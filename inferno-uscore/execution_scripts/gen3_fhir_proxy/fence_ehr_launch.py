#!/usr/bin/env python3
# fence_ehr_launch.py — Headless EHR launch for Fence with MOCK_AUTH.
#
# Simulates an EHR system launching Inferno as a SMART app by calling
# Inferno's launch URI with the iss and launch parameters, as required by
# the SMART App Launch v2 EHR launch flow.
#
# Fence must be configured with MOCK_AUTH: true so the subsequent OAuth
# authorization (handled by fence_authorize.py) can proceed without a real
# user login.
#
# Flow:
#   1. Build: {launch_uri}?iss={target_iss}&launch=mock_ehr_launch
#   2. GET that URL → Inferno matches the waiting test run by iss and
#      resumes the EHR launch test group (test 1.4.2.01 completes).
#   3. Inferno runs subsequent tests automatically until it reaches test
#      1.4.2.04 (waiting for OAuth callback) → fence_authorize.py handles that.
#
# Usage (called by inferno execute_script --allow-commands):
#   python3 execution_scripts/gen3_fhir_proxy/fence_ehr_launch.py '<launch_uri>' '<target_iss>'

import sys
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 30


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} '<launch_uri>' '<target_iss>'", file=sys.stderr)
        sys.exit(1)

    launch_uri, target_iss = sys.argv[1], sys.argv[2]
    sep = "&" if "?" in launch_uri else "?"
    url = f"{launch_uri}{sep}iss={urllib.parse.quote(target_iss, safe='')}&launch=mock_ehr_launch"

    print("[fence_ehr_launch] Initiating EHR launch")
    print(f"[fence_ehr_launch]   launch_uri : {launch_uri}")
    print(f"[fence_ehr_launch]   target_iss : {target_iss}")
    print(f"[fence_ehr_launch] Calling Inferno launch endpoint: {url}")

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": "inferno-fence-ehr-launch/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            print(f"[fence_ehr_launch]   → {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"[fence_ehr_launch]   → {e.code}")
        if e.code == 500:
            print("[fence_ehr_launch] ERROR: Inferno returned 500.", file=sys.stderr)
            sys.exit(1)

    print(
        "[fence_ehr_launch] Done. Inferno EHR launch triggered (test 1.4.2.01 should now complete)."
    )
    print(
        "[fence_ehr_launch] fence_authorize.py will handle the subsequent OAuth authorization (test 1.4.2.04)."
    )


if __name__ == "__main__":
    main()
