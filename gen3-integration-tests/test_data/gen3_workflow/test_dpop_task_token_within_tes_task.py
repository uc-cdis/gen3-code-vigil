"""
This script is used by the test of the same name in the `TestGen3Workflow` class
"""

import json
import os

import requests
from gen3.auth import Gen3Auth
from gen3.dpop import dpop_proxy_context

assert os.environ.get("API_KEY"), "No API_KEY env var"

auth = Gen3Auth(refresh_token={"api_key": os.environ["API_KEY"]})
with dpop_proxy_context(auth=auth, task_token_type="WORKFLOW") as (
    task_token,
    proxy_port,
):
    # query the most recent task created by this user
    res = requests.get(
        url=f"http://127.0.0.1:{proxy_port}/ga4gh/tes/v1/tasks?view=MINIMAL&page_size=1&tag_key=TEST_NAME&tag_value=test_dpop_task_token_within_tes_task",
        headers={"Authorization": f"bearer {task_token}"},
    )
    assert res.status_code == 200, res.text

    # write the result to the output file
    with open("output.json", "w", encoding="utf-8") as file:
        file.write(json.dumps(res.json()))
