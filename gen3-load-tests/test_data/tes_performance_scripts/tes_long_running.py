import datetime
import json
import os
import time

import requests
from gen3.auth import Gen3Auth
from gen3.dpop import dpop_proxy_context

assert os.environ.get("API_KEY"), "No API_KEY env var"
assert os.environ.get("RUN_N_HOURS"), "No RUN_N_HOURS env var"

auth = Gen3Auth(refresh_token={"api_key": os.environ["API_KEY"]})
n_hours = float(os.environ["RUN_N_HOURS"])
print(f"Configured to run for {n_hours} hours...")

start_time = time.time()
end_time = start_time + n_hours * 60 * 60
sleep_min = 15
while time.time() < end_time:
    # TODO every 15 or 30 min (only sleep 5 min so we don't sleep too much past the configured runtime)
    print(
        f"I have been running for {datetime.timedelta(seconds=time.time()-start_time)}"
    )

    # TODO fetch a file or something
    with dpop_proxy_context(
        auth=auth, task_token_type="WORKFLOW", task_token_expiration=30
    ) as (
        task_token,
        proxy_port,
    ):
        res = requests.get(
            url=f"http://127.0.0.1:{proxy_port}/ga4gh/tes/v1/tasks?view=MINIMAL&page_size=1&tag_key=TEST_NAME&tag_value=test_dpop_task_token_within_tes_task",
            headers={"Authorization": f"bearer {task_token}"},
        )
        msg = f"Request to /ga4gh/tes/v1/tasks: {res.status_code}"
        if res.status_code != 200:
            msg += f" - {res.text}"
        print(msg)
    time.sleep(60 * sleep_min)

# TODO move to new integration test
# or maybe not? the TES pod can't reach the local proxy's URL
# res = requests.get(
#     url=f"{os.environ["proxy_url"]}/ga4gh/tes/v1/tasks?view=MINIMAL&page_size=1&tag_key=TEST_NAME&tag_value=test_dpop_task_token_within_tes_task",
#     # url=f"http://127.0.0.1:{proxy_port}/ga4gh/tes/v1/tasks?view=MINIMAL&page_size=1&tag_key=TEST_NAME&tag_value=test_dpop_task_token_within_tes_task",
#     headers={"Authorization": f"bearer {os.environ["DPOP_TOKEN"]}"},
# )
# assert res.status_code == 200, res.text

# # write the result to the output file
# with open("output.json", "w", encoding="utf-8") as file:
#     file.write(json.dumps(res.json()))
