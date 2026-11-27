"""
Pytest fixtures for Inferno US Core tests.

Manages the Inferno server lifecycle: overlays gen3 config, starts background
services (Redis + HL7 Validator), runs DB migrations, starts the Inferno server,
and tears everything down on exit.

Prerequisites:
  - Ruby 3.3.x with bundler, us-core-test-kit repo checked out and bundle-installed
    (set US_CORE_TEST_KIT_DIR, default: ~/us-core-test-kit)
  - Docker Desktop running
  - INFERNO_CLIENT_ID, INFERNO_GRANULAR1_CLIENT_ID, INFERNO_GRANULAR2_CLIENT_ID set
  - gen3-fhir-proxy + Fence reachable (set FHIR_CHECK_URL if non-default)
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

import httpx
import pytest

_REPO_ROOT = Path(__file__).parent.parent
_US_CORE_DIR = Path(
    os.environ.get("US_CORE_TEST_KIT_DIR", Path.home() / "us-core-test-kit")
)
_INFERNO_PORT = int(os.environ.get("INFERNO_PORT", "4567"))
_INFERNO_BASE = f"http://localhost:{_INFERNO_PORT}"
_FHIR_CHECK_URL = os.environ.get(
    "FHIR_CHECK_URL", "http://localhost:8081/fhir/metadata"
)


def _overlay_gen3_config() -> None:
    """Copy gen3 Inferno config files into the us-core-test-kit checkout."""
    for sub in ("data/redis", "data/igs", "data/logs"):
        (_US_CORE_DIR / sub).mkdir(parents=True, exist_ok=True)

    for src, dst in [
        (
            _REPO_ROOT / "docker-compose.background.yml",
            _US_CORE_DIR / "docker-compose.background.yml",
        ),
        (_REPO_ROOT / ".env.production", _US_CORE_DIR / ".env.production"),
        (_REPO_ROOT / "config/nginx.conf", _US_CORE_DIR / "config/nginx.conf"),
        (
            _REPO_ROOT / "config/nginx.background.conf",
            _US_CORE_DIR / "config/nginx.background.conf",
        ),
    ]:
        shutil.copy2(src, dst)

    exec_dst = _US_CORE_DIR / "execution_scripts/gen3_fhir_proxy"
    exec_dst.mkdir(parents=True, exist_ok=True)
    for f in (_REPO_ROOT / "execution_scripts/gen3_fhir_proxy").iterdir():
        shutil.copy2(f, exec_dst / f.name)

    preset_dst = _US_CORE_DIR / "config/presets"
    preset_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        _REPO_ROOT / "config/presets/gen3_fhir_proxy_610_preset.json",
        preset_dst / "gen3_fhir_proxy_610_preset.json",
    )


@pytest.fixture(scope="session")
def client_ids() -> dict:
    """Return Fence OAuth client IDs from env vars, skipping if any are missing."""
    missing = [
        v
        for v in (
            "INFERNO_CLIENT_ID",
            "INFERNO_GRANULAR1_CLIENT_ID",
            "INFERNO_GRANULAR2_CLIENT_ID",
        )
        if not os.environ.get(v)
    ]
    if missing:
        pytest.skip(f"Missing required env vars: {', '.join(missing)}")
    return {
        "main": os.environ["INFERNO_CLIENT_ID"],
        "granular1": os.environ["INFERNO_GRANULAR1_CLIENT_ID"],
        "granular2": os.environ["INFERNO_GRANULAR2_CLIENT_ID"],
    }


@pytest.fixture(scope="session")
def inferno_url(client_ids) -> str:  # noqa: F811
    """
    Start Inferno services + server; yield base URL; tear down on exit.

    Depends on client_ids to skip early if credentials are missing.
    """
    if not _US_CORE_DIR.is_dir() or not (_US_CORE_DIR / "Gemfile").exists():
        pytest.skip(
            f"us-core-test-kit not found at {_US_CORE_DIR} — set US_CORE_TEST_KIT_DIR"
        )

    _overlay_gen3_config()

    # Start background services (Redis, HL7 Validator, nginx)
    subprocess.run(
        ["bundle", "exec", "inferno", "services", "start"],
        cwd=_US_CORE_DIR,
        check=True,
    )

    # Wait for Redis
    for i in range(30):
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "docker-compose.background.yml",
                "exec",
                "-T",
                "redis",
                "redis-cli",
                "ping",
            ],
            cwd=_US_CORE_DIR,
            capture_output=True,
        )
        if b"PONG" in result.stdout:
            break
        if i == 29:
            pytest.fail("Redis did not become ready within 60s")
        time.sleep(2)

    subprocess.run(
        ["bundle", "exec", "inferno", "migrate"], cwd=_US_CORE_DIR, check=True
    )

    # Start Inferno server in the background
    proc = subprocess.Popen(
        ["bundle", "exec", "inferno", "start"],
        cwd=_US_CORE_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for i in range(60):
        try:
            httpx.get(_INFERNO_BASE, timeout=2)
            break
        except Exception:
            if i == 59:
                proc.terminate()
                pytest.fail(f"Inferno did not start at {_INFERNO_BASE} within 120s")
            time.sleep(2)

    yield _INFERNO_BASE

    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()

    subprocess.run(
        ["bundle", "exec", "inferno", "services", "stop"],
        cwd=_US_CORE_DIR,
        check=False,
    )
