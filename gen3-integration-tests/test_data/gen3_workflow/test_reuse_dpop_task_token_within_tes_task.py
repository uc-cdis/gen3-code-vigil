"""
This script is used by the test of the same name in the `TestGen3Workflow` class
"""

import os

import requests
from gen3.auth import Gen3Auth
from gen3.dpop import dpop_proxy_context

assert os.environ.get("API_KEY"), "No API_KEY env var"
assert os.environ.get("REUSED_TASK_TOKEN"), "No REUSED_TASK_TOKEN env var"

auth = Gen3Auth(refresh_token={"api_key": os.environ["API_KEY"]})
with dpop_proxy_context(auth=auth, task_token_type="WORKFLOW") as (_, proxy_port):
    # attempt to use the token to hit the TES API
    res = requests.get(
        url=f"http://127.0.0.1:{proxy_port}/ga4gh/tes/v1/tasks?view=MINIMAL&page_size=1",
        headers={"Authorization": f"bearer {os.environ['REUSED_TASK_TOKEN']}"},
    )
    assert res.status_code == 401, res.text
    assert res.text == "Unauthorized"
