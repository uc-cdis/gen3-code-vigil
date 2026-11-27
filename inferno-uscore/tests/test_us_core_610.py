"""
Inferno US Core v6.1.0 integration test for gen3-fhir-proxy.

Drives the Inferno server via its JSON REST API, eliminating the
execute_script YAML mechanism and Ruby hook scripts. Each SMART App Launch
OAuth waiting state is handled inline by Python HTTP calls that mirror
fence_authorize.py and fence_ehr_launch.py.

Prerequisites: see conftest.py.

Run:
  cd inferno-uscore
  INFERNO_CLIENT_ID=... INFERNO_GRANULAR1_CLIENT_ID=... INFERNO_GRANULAR2_CLIENT_ID=... \\
    pytest tests/test_us_core_610.py -v
"""

import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

import httpx
import pytest

_REPO_ROOT = Path(__file__).parent.parent
_FHIR_ENDPOINT = os.environ.get(
    "INFERNO_FHIR_ENDPOINT", "http://host.docker.internal:8081/fhir"
)
_BASELINE_PATH = (
    _REPO_ROOT
    / "execution_scripts/gen3_fhir_proxy/gen3_fhir_proxy_610_smart_2_expected.json"
)
_SUITE_ID = "us_core_v610"
_PRESET_ID = "us_core_v610_vs_gen3_fhir_proxy"
_MAX_REDIRECTS = 20
_HTTP_TIMEOUT = 30


# ── Inferno REST client ──────────────────────────────────────────────────────


class InfernoClient:
    def __init__(self, base_url: str) -> None:
        self._http = httpx.Client(base_url=base_url, timeout=30)

    def create_session(self) -> str:
        resp = self._http.post(
            "/api/test_sessions",
            json={
                "test_suite_id": _SUITE_ID,
                "preset_id": _PRESET_ID,
                "suite_options": [
                    {"id": "smart_app_launch_version", "value": "smart_app_launch_2"}
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def start_run(
        self,
        session_id: str,
        group_id: str,
        inputs: Optional[dict] = None,
    ) -> str:
        body: dict = {"test_session_id": session_id, "test_group_id": group_id}
        if inputs:
            body["inputs"] = [{"name": k, "value": v} for k, v in inputs.items()]
        resp = self._http.post("/api/test_runs", json=body)
        resp.raise_for_status()
        return resp.json()["id"]

    def get_last_run(self, session_id: str) -> dict:
        resp = self._http.get(f"/api/test_sessions/{session_id}/last_test_run")
        resp.raise_for_status()
        return resp.json()

    def get_wait_outputs(self, run_id: str) -> dict:
        resp = self._http.get(f"/api/test_runs/{run_id}/results")
        resp.raise_for_status()
        for result in resp.json():
            if result.get("result") == "wait":
                return {o["name"]: o["value"] for o in result.get("outputs", [])}
        return {}

    def get_session_results(self, session_id: str) -> list:
        resp = self._http.get(f"/api/test_sessions/{session_id}/results")
        resp.raise_for_status()
        return resp.json()


# ── OAuth helpers ────────────────────────────────────────────────────────────


def _fence_ehr_launch(launch_uri: str, target_iss: str) -> None:
    """Trigger the EHR launch endpoint on Inferno (simulates an EHR redirect)."""
    sep = "&" if "?" in launch_uri else "?"
    url = f"{launch_uri}{sep}iss={urllib.parse.quote(target_iss, safe='')}&launch=mock_ehr_launch"
    req = urllib.request.Request(
        url, headers={"User-Agent": "inferno-fence-ehr-launch/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
            if resp.status == 500:
                raise RuntimeError("Inferno returned 500 on EHR launch")
    except urllib.error.HTTPError as exc:
        if exc.code == 500:
            raise RuntimeError("Inferno returned 500 on EHR launch") from exc


def _http_request(
    url: str,
    method: str = "GET",
    form_data: Optional[dict] = None,
    cookies: Optional[dict] = None,
) -> tuple[int, str, Optional[str], dict]:
    """Single HTTP request; returns (status, body, location, updated_cookies)."""
    parsed = urllib.parse.urlparse(url)
    conn = (
        http.client.HTTPSConnection(
            parsed.hostname, parsed.port or 443, timeout=_HTTP_TIMEOUT
        )
        if parsed.scheme == "https"
        else http.client.HTTPConnection(
            parsed.hostname, parsed.port or 80, timeout=_HTTP_TIMEOUT
        )
    )
    path = (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "User-Agent": "inferno-fence-authorize/1.0",
    }
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
    body = None
    if form_data:
        body = urllib.parse.urlencode(form_data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    conn.request(method, path, body=body, headers=headers)
    resp = conn.getresponse()
    body_text = resp.read().decode("utf-8", errors="replace")

    new_cookies = dict(cookies or {})
    for sc in resp.getheaders("Set-Cookie"):
        nv = sc.split(";")[0].strip()
        if "=" in nv:
            k, v = nv.split("=", 1)
            new_cookies[k.strip()] = v.strip()

    location = resp.getheader("Location")
    if location:
        lp = urllib.parse.urlparse(location)
        if not lp.netloc:
            location = urllib.parse.urlunparse(
                lp._replace(scheme=parsed.scheme, netloc=parsed.netloc)
            )

    return resp.status, body_text, location, new_cookies


def _fence_authorize(auth_url: str) -> None:
    """
    Drive the SMART authorization redirect chain through Fence with MOCK_AUTH.

    Appends confirm=yes to skip the consent page, then follows all redirects
    back to Inferno's callback URL with cookie persistence.
    """
    sep = "&" if "?" in auth_url else "?"
    url = f"{auth_url}{sep}confirm=yes"
    cookies: dict = {}

    for _ in range(_MAX_REDIRECTS):
        status, body, location, cookies = _http_request(url, cookies=cookies)
        if 300 <= status < 400:
            if not location:
                return
            url = location
        elif status == 200:
            # Fallback: consent page was rendered — POST confirm=yes
            if "confirm" in body and (
                "oauth" in body or "authorize" in body or "scope" in body
            ):
                consent_url = url.split("?")[0]
                status, _, location, cookies = _http_request(
                    consent_url,
                    method="POST",
                    form_data={"confirm": "yes"},
                    cookies=cookies,
                )
                if 300 <= status < 400 and location:
                    url = location
                    continue
            return
        else:
            raise RuntimeError(f"OAuth flow failed: HTTP {status} at {url}")

    raise RuntimeError(f"Too many redirects (> {_MAX_REDIRECTS})")


# ── Run driver ───────────────────────────────────────────────────────────────


def _run_until_done(
    client: InfernoClient,
    session_id: str,
    run_id: str,
    timeout_secs: int = 600,
) -> dict:
    """
    Poll a test run until 'done', injecting OAuth flows on each 'waiting' state.

    Uses run_id to skip stale last_test_run responses that still reflect the
    previous group before Inferno registers the new one.
    """
    deadline = time.monotonic() + timeout_secs

    while time.monotonic() < deadline:
        run = client.get_last_run(session_id)

        # Inferno may briefly return the previous (done) run; wait for the new one
        if run.get("id") != run_id:
            time.sleep(1)
            continue

        status = run.get("status", "unknown")

        if status == "done":
            return run

        if status == "waiting":
            outputs = client.get_wait_outputs(run_id)
            if "authorization_url" in outputs:
                _fence_authorize(outputs["authorization_url"])
            elif "launch_uri" in outputs and "target_iss" in outputs:
                _fence_ehr_launch(outputs["launch_uri"], outputs["target_iss"])
            else:
                raise RuntimeError(f"Unexpected wait outputs: {sorted(outputs)}")
            # Give Inferno time to process the callback before re-polling
            time.sleep(2)
            continue

        # queued / running: keep waiting
        time.sleep(2)

    raise TimeoutError(
        f"Run {run_id} (group in session {session_id}) did not complete "
        f"within {timeout_secs}s — last status: {run.get('status')}"
    )


# ── Baseline comparison ──────────────────────────────────────────────────────


def _check_against_baseline(results: list, baseline_path: Path) -> list[str]:
    """Return a list of mismatch descriptions (empty = all pass)."""
    baseline = json.loads(baseline_path.read_text())

    def _key(entry: dict) -> Optional[str]:
        return (
            entry.get("test_id")
            or entry.get("test_group_id")
            or entry.get("test_suite_id")
        )

    baseline_map = {_key(e): e["result"] for e in baseline if _key(e)}
    actual_map = {_key(e): e.get("result", "unknown") for e in results if _key(e)}

    return [
        f"  {k}: expected={expected}, actual={actual_map.get(k, 'MISSING')}"
        for k, expected in baseline_map.items()
        if actual_map.get(k, "MISSING") != expected
    ]


# ── Test ─────────────────────────────────────────────────────────────────────


@pytest.mark.inferno_uscore
def test_us_core_610(inferno_url: str, client_ids: dict) -> None:
    """
    Drive the full Inferno US Core v6.1.0 suite via the Inferno REST API.

    Runs all SMART App Launch and FHIR API groups in sequence, injects Fence
    MOCK_AUTH OAuth flows for each waiting state, and asserts that every
    result matches the committed baseline.
    """
    client = InfernoClient(inferno_url)
    session_id = client.create_session()

    def _auth(cid: str) -> dict:
        return {"auth_type": "public", "use_discovery": True, "client_id": cid}

    def _run(group_id: str, inputs: Optional[dict] = None, timeout: int = 600) -> None:
        run_id = client.start_run(session_id, group_id, inputs)
        _run_until_done(client, session_id, run_id, timeout_secs=timeout)

    # ── SMART App Launch ──────────────────────────────────────────────────
    _run(
        "1.3",
        inputs={"url": _FHIR_ENDPOINT, "smart_auth_info": _auth(client_ids["main"])},
    )
    _run("1.4")  # EHR launch: two waiting states handled automatically

    # ── US Core FHIR API ──────────────────────────────────────────────────
    _run("2", timeout=3600)

    # ── Granular Scopes 1 ─────────────────────────────────────────────────
    _run(
        "3.1.1.1",
        inputs={"granular_scopes_1_auth_info": _auth(client_ids["granular1"])},
    )
    _run("3.1.1.3")  # EHR launch: two waiting states
    _run("3.1.2", timeout=600)

    # ── Granular Scopes 2 ─────────────────────────────────────────────────
    _run(
        "3.2.1.1",
        inputs={"granular_scopes_2_auth_info": _auth(client_ids["granular2"])},
    )
    _run("3.2.1.3")  # EHR launch: two waiting states
    _run("3.2.2", timeout=600)

    # ── Compare to baseline ───────────────────────────────────────────────
    if _BASELINE_PATH.exists():
        results = client.get_session_results(session_id)
        mismatches = _check_against_baseline(results, _BASELINE_PATH)
        assert not mismatches, (
            f"Inferno US Core results differ from baseline "
            f"({len(mismatches)} mismatch(es)):\n" + "\n".join(mismatches)
        )
