#!/usr/bin/env python3
# fence_authorize.py — Headless OAuth standalone/EHR launch authorization for Fence with MOCK_AUTH.
#
# Drives the SMART authorization redirect chain (Fence → consent → Inferno callback)
# using a plain HTTP client with cookie persistence. No browser required.
#
# Requires MOCK_AUTH: true in the Fence config (bypasses OIDC login; always authenticates
# as the "test" user). With MOCK_AUTH, Fence's /oauth2/authorize endpoint auto-authenticates
# and either redirects directly to the callback URL (if the client has auto_approve=True) or
# renders a consent page. This script follows all redirects and also handles the consent step
# by POSTing confirm=yes to the consent URL.
#
# Usage (called by inferno execute_script --allow-commands):
#   python3 execution_scripts/gen3_fhir_proxy/fence_authorize.py '<authorization_url>'

import http.client
import sys
import urllib.parse

MAX_REDIRECTS = 20
TIMEOUT = 30

_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "User-Agent": "inferno-fence-authorize/1.0",
}


def _connect(parsed):
    if parsed.scheme == "https":
        return http.client.HTTPSConnection(
            parsed.hostname, parsed.port or 443, timeout=TIMEOUT
        )
    return http.client.HTTPConnection(
        parsed.hostname, parsed.port or 80, timeout=TIMEOUT
    )


def _request(url, method="GET", form_data=None, cookies=None):
    parsed = urllib.parse.urlparse(url)
    conn = _connect(parsed)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query

    headers = dict(_HEADERS)
    if cookies:
        headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())

    body = None
    if form_data:
        body = urllib.parse.urlencode(form_data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    print(f"[fence_authorize] {method} {parsed.scheme}://{parsed.netloc}{path}")
    conn.request(method, path, body=body, headers=headers)
    resp = conn.getresponse()
    body_text = resp.read().decode("utf-8", errors="replace")
    print(f"[fence_authorize]   → {resp.status}")

    new_cookies = dict(cookies or {})
    for set_cookie in resp.getheaders("Set-Cookie"):
        name_value = set_cookie.split(";")[0].strip()
        if "=" in name_value:
            k, v = name_value.split("=", 1)
            new_cookies[k.strip()] = v.strip()

    location = resp.getheader("Location")
    if location:
        loc_parsed = urllib.parse.urlparse(location)
        if not loc_parsed.netloc:
            location = urllib.parse.urlunparse(
                loc_parsed._replace(scheme=parsed.scheme, netloc=parsed.netloc)
            )

    return resp.status, body_text, location, new_cookies


def follow_redirects(start_url, cookies):
    url = start_url
    for _ in range(MAX_REDIRECTS):
        status, body, location, cookies = _request(url, cookies=cookies)
        if 300 <= status < 400:
            if not location:
                print("[fence_authorize] Redirect with no Location — stopping.")
                return
            url = location
        elif status == 200:
            # Fence may render a consent page when auto_approve is not set.
            # Detect it and POST confirm=yes to complete the authorization.
            if "confirm" in body and (
                "oauth" in body or "authorize" in body or "scope" in body
            ):
                print(
                    "[fence_authorize] Consent page detected — submitting confirm=yes"
                )
                consent_url = url.split("?")[0]
                status, _, location, cookies = _request(
                    consent_url,
                    method="POST",
                    form_data={"confirm": "yes"},
                    cookies=cookies,
                )
                if 300 <= status < 400 and location:
                    url = location
                    continue
            print(
                "[fence_authorize] Reached destination (HTTP 200). OAuth flow complete."
            )
            return
        else:
            print(
                f"[fence_authorize] Unexpected HTTP {status} at {url}", file=sys.stderr
            )
            sys.exit(f"OAuth flow failed with HTTP {status}")
    sys.exit(f"Too many redirects (> {MAX_REDIRECTS})")


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} '<authorization_url>'", file=sys.stderr)
        sys.exit(1)

    auth_url = sys.argv[1]
    # Append confirm=yes so Fence skips the consent page and immediately issues the
    # authorization code. Fence's /oauth2/authorize checks request.args.get("confirm")
    # before rendering the consent form (see fence/blueprints/oauth2.py).
    sep = "&" if "?" in auth_url else "?"
    auth_url = f"{auth_url}{sep}confirm=yes"
    print(f"[fence_authorize] Starting OAuth flow from: {auth_url}")
    print("[fence_authorize] Auto-confirming consent (confirm=yes)")

    follow_redirects(auth_url, {})
    print("[fence_authorize] Done.")


if __name__ == "__main__":
    main()
