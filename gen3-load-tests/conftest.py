import json
import os
import shutil
from datetime import datetime, timedelta

import boto3
import pytest

# Using dotenv to simplify setting up env vars locally
from dotenv import load_dotenv
from utils import LOAD_TESTING_OUTPUT_PATH, TEST_DATA_PATH_OBJECT, logger
from utils import test_setup as setup

load_dotenv()
collect_ignore = ["test_setup.py"]


def pytest_configure(config):
    # Compute hostname and namespace
    pytest.namespace = os.getenv("NAMESPACE")
    pytest.hostname = os.getenv("HOSTNAME")
    # Compute root_url
    pytest.root_url = f"https://{pytest.hostname}"

    # Generate api key and auth headers
    pytest.users = {
        "main_account": "main@example.org",
        "indexing_account": "indexing@example.org",
    }

    # Minimum pass percentage for each load test
    pytest.pass_threshold = 98
    pytest.api_keys = {}
    for user in pytest.users:
        pytest.api_keys[user] = setup.get_api_key(user)

    LOAD_TESTING_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    setup.perform_pre_load_testing_setup()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_logreport(report):
    yield

    if report.when != "call":
        return

    test_nodeid = report.nodeid
    start_time = datetime.fromtimestamp(report.start)
    file_name = test_nodeid.split("::")[-1].replace("test_", "").replace("_", "-")
    output_path = LOAD_TESTING_OUTPUT_PATH / f"{file_name}.json"
    output = json.loads(output_path.read_text())
    metrics = output.get("metrics", {})
    message = {
        "run_date": str(start_time.date()),
        "run_num": os.getenv("RUN_NUM"),
        "release_version": os.getenv("RELEASE_VERSION"),
        "test_suite": test_nodeid.split("::")[1],
        "test_case": test_nodeid.split("::")[-1],
        "result": report.outcome,
        "checks_fails": metrics["checks"]["fails"],
        "checks_passes": metrics["checks"]["passes"],
        "checks_value": metrics["checks"]["value"],
        "http_req_duration_avg": metrics["http_req_duration"]["avg"],
        "http_req_duration_min": metrics["http_req_duration"]["min"],
        "http_req_duration_med": metrics["http_req_duration"]["med"],
        "http_req_duration_max": metrics["http_req_duration"]["max"],
        "http_req_duration_p90": metrics["http_req_duration"]["p(90)"],
        "http_req_duration_p95": metrics["http_req_duration"]["p(95)"],
        "data_sent_count": metrics["data_sent"]["count"],
        "data_sent_rate": metrics["data_sent"]["rate"],
        "iterations_count": metrics["iterations"]["count"],
        "iterations_rate": metrics["iterations"]["rate"],
        "bulk_objects_requested_count": metrics.get("bulk_objects_requested", {}).get(
            "count"
        ),
        "bulk_objects_requested_rate": metrics.get("bulk_objects_requested", {}).get(
            "rate"
        ),
        "bulk_objects_resolved_count": metrics.get("bulk_objects_resolved", {}).get(
            "count"
        ),
        "bulk_objects_resolved_rate": metrics.get("bulk_objects_resolved", {}).get(
            "rate"
        ),
        "bulk_objects_unresolved_count": metrics.get("bulk_objects_unresolved", {}).get(
            "count"
        ),
        "bulk_objects_unresolved_rate": metrics.get("bulk_objects_unresolved", {}).get(
            "rate"
        ),
        "partial_bulk_responses_rate": metrics.get("partial_bulk_responses", {}).get(
            "rate"
        ),
    }

    try:
        sqs = boto3.client("sqs")
        queue_url = (
            "https://sqs.us-east-1.amazonaws.com/707767160287/load-test-metrics-sqs"
        )
        response = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(message))
        logger.info(f"[SQS MESSAGE SENT] MessageId: {response['MessageId']}")
    except Exception as e:
        logger.error(f"[SQS SEND ERROR] {e}")


def pytest_unconfigure(config):
    if not hasattr(config, "workerinput"):
        directory_path = TEST_DATA_PATH_OBJECT / "generated_metadata_service_template"
        if os.path.exists(directory_path):
            shutil.rmtree(directory_path)
