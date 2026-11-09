# pylint: disable=missing-function-docstring

import json
import math
import os
import sys
import time

import backoff
import requests
from cdislogging import get_logger
from dateutil import parser
from gen3.utils import BACKOFF_NO_LOG_IF_NOT_RETRIED

logger = get_logger("run_tes_task", log_level="debug")


BACKOFF_SETTINGS = {
    **BACKOFF_NO_LOG_IF_NOT_RETRIED,
    "base": 3,
    "factor": 5,
    # wait up to 5 min between calls, regardless of how many tries it takes to get to 5 min
    "max_value": 300,
    "max_tries": None,
}


class RetryableException(Exception):
    pass


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


@backoff.on_exception(backoff.expo, RetryableException, **BACKOFF_SETTINGS)
def get_task_with_backoff_retry(endpoint, task_id):
    response = requests.get(
        f"{endpoint}/ga4gh/tes/v1/tasks/{task_id}?view=FULL",
        headers={"authorization": f"bearer {os.environ['GEN3_TOKEN']}"},
        timeout=60,
    )
    if response.status_code != 200:
        msg = f"Getting task '{task_id}': got status code {response.status_code}"
        logger.error(f"{msg}. Details: {response.text}")
        if response.status_code in [408, 409, 429, 502, 503, 504]:
            raise RetryableException(msg)

    assert response.status_code == 200, response.text
    return response.json()


def cancel_task(endpoint, task_id):
    response = requests.post(
        url=f"{endpoint}/ga4gh/tes/v1/tasks/{task_id}:cancel",
        headers={"authorization": f"bearer {os.environ['GEN3_TOKEN']}"},
    )
    assert response.status_code == 200, response.text


def monitor_task(endpoint, task_id):
    sleep_time = 5
    max_attempt = math.ceil(int(float(os.environ["TIMEOUT"])) / sleep_time)
    status = None
    data = {}
    for _ in range(max_attempt):
        data = get_task_with_backoff_retry(endpoint, task_id)
        status = data["state"]
        logger.debug(f"Task status: {status}")
        if status == "COMPLETE":
            logger.info("Task complete!")
            return status, data
        if status in ["SYSTEM_ERROR", "EXECUTOR_ERROR"]:
            logger.info("Task failed")
            return status, data
        time.sleep(sleep_time)
    logger.info(f"Task did not complete in time ({max_attempt} attempts)")
    cancel_task(endpoint, task_id)
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
            logger.warning(
                f"Runtime: unknown. Unable to parse task start_time ({start_time}) and end_time ({end_time}): {e}"
            )
        else:
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            logger.info(f"Runtime: {hours}h {minutes}m {seconds}s")
    else:
        logger.info(json.dumps(task_data, indent=2))
        raise Exception("Task failed or did not complete")


if __name__ == "__main__":
    try:
        assert len(sys.argv) == 3, "Incorrect number of arguments"
        main(sys.argv[1], json.loads(sys.argv[2]))
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
