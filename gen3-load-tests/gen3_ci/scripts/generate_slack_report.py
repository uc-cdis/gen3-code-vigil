import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from utils import logger


def get_test_result_and_metrics():
    allure_summary_path = (
        Path(__file__).parent.parent.parent
        / "allure-report"
        / "widgets"
        / "summary.json"
    )
    if allure_summary_path.exists():
        with open(allure_summary_path) as f:
            summary_json = json.load(f)
        statistic_json = summary_json["statistic"]
        time_json = summary_json.get("time", {})
        total = int(statistic_json["total"])
        passed = int(statistic_json["passed"])
        skipped = int(statistic_json["skipped"])
        failed = (
            int(statistic_json["failed"])
            + int(statistic_json["broken"])
            + int(statistic_json["unknown"])
        )  # some broken tests are reported as Unknown
        # duration rounded to the minute
        test_duration = (
            round(int(time_json["duration"]) / 60000, 2)
            if "duration" in time_json
            else "?"
        )
        if total == 0:  # If no test runs on a PR treat it as failed
            test_result = "Failed"
        elif passed + skipped == total:
            test_result = "Successful"
        else:
            test_result = "Failed"
        test_metrics_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Test Metrics*:   :white_check_mark: Passed - {passed}    :x: Failed  - {failed}    :large_yellow_circle: Skipped  - {skipped}    :stopwatch: Test Run Time - {test_duration} minutes",
            },
        }
        return (test_result, test_metrics_block)
    else:
        return ("Failed", None)


def generate_slack_report():
    report_link = f"https://allure.ci.planx-pla.net/load-tests/{datetime.now().strftime('%Y%m%d')}/index.html"
    slack_report_json = {}
    # Fetch run result and test metrics
    test_result, test_metrics_block = get_test_result_and_metrics()
    test_result_icons = {"Successful": ":tada:", "Failed": ":fire:"}
    slack_report_json["text"] = f"Load Test Result: {os.getenv("RELEASE_VERSION")}"
    slack_report_json["blocks"] = []
    # Header
    header_block = {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "Load Test Results",
            "emoji": True,
        },
    }
    slack_report_json["blocks"].append(header_block)
    # Calculate gh action time
    start_time = os.getenv("GITHUB_RUN_STARTED_AT")
    logger.info(f"GITHUB_RUN_STARTED_AT: {start_time}")
    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    gh_duration = round((datetime.now(timezone.utc) - start_dt).total_seconds() / 60, 2)
    # Run summary
    summary_block = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"{test_result_icons[test_result]} {test_result} run for {os.getenv("RELEASE_VERSION")} on :round_pushpin:*{os.getenv('NAMESPACE')}* (took :stopwatch: *{gh_duration} minutes*)",
        },
    }
    slack_report_json["blocks"].append(summary_block)
    # Test metrics
    if test_metrics_block:
        slack_report_json["blocks"].append(test_metrics_block)
        report_link_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Test Report*: <{report_link}|click here>",
            },
        }
        slack_report_json["blocks"].append(report_link_block)
    else:
        logger.info(
            "Allure report was not found. Skipping test metrics block generation."
        )

    slack_report_json["channel"] = "#gen3-release-notifications"
    # DEBUG LOGS
    print(slack_report_json)

    json.dump(slack_report_json, open("slack_report.json", "w"))


if __name__ == "__main__":
    logger.info("Generating slack report ...")
    generate_slack_report()
