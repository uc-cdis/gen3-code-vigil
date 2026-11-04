import datetime
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
sleep_min = 5
i = 0
while time.time() < end_time:
    print(
        f"I have been running for {datetime.timedelta(seconds=time.time()-start_time)}"
    )

    if i % 6 == 0:
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
    i += 1

print("Done!")
