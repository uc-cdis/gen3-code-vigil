# pylint: disable=missing-function-docstring

import json
import math
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
        f"{endpoint}/ga4gh/tes/v1/tasks",
        json=body,
        headers={"authorization": f"bearer {os.environ['GEN3_TOKEN']}"},
        timeout=60,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    return data["id"]


def monitor_task(endpoint, task_id):
    sleep_time = 5
    max_attempt = math.ceil(int(os.environ["TIMEOUT"]) / sleep_time)
    status = None
    data = {}
    for attempt in range(max_attempt):
        response = requests.get(
            f"{endpoint}/ga4gh/tes/v1/tasks/{task_id}?view=FULL",
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
        if attempt == max_attempt - 1:
            log("info", f"Task did not complete in time ({max_attempt} attempts)")
            break
        time.sleep(sleep_time)
    return status, data


def main(endpoint, body):
    """
    Submits a single TES (Task Execution Service) task and polls until it completes or fails.

    Usage:
        python run_tes_task.py <endpoint> <task_body_json>

    Arguments:
        endpoint        - Base URL of the TES-compatible endpoint.
        task_body_json  - JSON string conforming to the GA4GH TES Task schema.

    Environment variables required:
        GEN3_TOKEN  - Bearer token for authenticating requests to the TES API.

    On success prints the task runtime (hours/minutes/seconds) and exits 0.
    On failure or timeout (>10 min) prints the full task payload and exits 1.
    """
    task_id = create_task(endpoint, body)
    status, task_data = monitor_task(endpoint, task_id)
    if status == "COMPLETE":
        start_time = task_data.get("logs", [{}])[0].get("start_time")
        end_time = task_data.get("logs", [{}])[0].get("end_time")
        try:
            duration = parser.parse(end_time) - parser.parse(start_time)
        except Exception as e:
            print(
                f"Runtime: unknown. Unable to parse task start_time ({start_time}) and end_time ({end_time}): {e}"
            )
        else:
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
