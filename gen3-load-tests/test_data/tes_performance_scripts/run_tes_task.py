# pylint: disable=missing-function-docstring

import json
import os
import sys
import time

import requests
from dateutil import parser

VERBOSE = False


def log(level, msg):
    if level == "debug" and not VERBOSE:
        return
    print(msg)


def create_task(endpoint, body):
    response = requests.post(
        f"{endpoint}/workflows/ga4gh/tes/v1/tasks",
        json=body,
        headers={"authorization": f"bearer {os.environ['GEN3_TOKEN']}"},
        timeout=60,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    return data["id"]


def monitor_task(endpoint, task_id):
    max_i = 120  # wait up to 10 min
    status = None
    data = {}
    for i in range(max_i):
        response = requests.get(
            f"{endpoint}/workflows/ga4gh/tes/v1/tasks/{task_id}?view=FULL",
            headers={"authorization": f"bearer {os.environ['GEN3_TOKEN']}"},
            timeout=60,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        status = data["state"]
        log("debug", f"Task status: {status}")
        if status == "COMPLETE":
            log("info", "Task complete!")
            break
        if status in ["SYSTEM_ERROR", "EXECUTOR_ERROR"]:
            log("info", "Task failed")
            break
        if i == max_i - 1:
            log("info", "Task did not complete in time")
            break
        time.sleep(5)
    return status, data


def main(endpoint, body):
    task_id = create_task(endpoint, body)
    status, task_data = monitor_task(endpoint, task_id)
    if status == "COMPLETE":
        start_time = task_data.get("logs", [{}])[0].get("start_time")
        end_time = task_data.get("logs", [{}])[0].get("end_time")
        duration = parser.parse(end_time) - parser.parse(start_time)
        total_seconds = int(duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        print(f"Runtime: {hours}h {minutes}m {seconds}s")
    else:
        print(json.dumps(task_data, indent=2))
        raise Exception("Task failed or did not complete")


if __name__ == "__main__":
    try:
        assert len(sys.argv) == 3, "Incorrect number of arguments"
        main(sys.argv[1], json.loads(sys.argv[2]))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
