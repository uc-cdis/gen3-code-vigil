import csv
import json
import os
from datetime import datetime
from pathlib import Path

from utils import logger


def get_failed_suites():
    suite_report_path = (
        Path(__file__).parent.parent.parent / "allure-report" / "data" / "suites.csv"
    )
    if suite_report_path.exists:
        failed_suites = set()
        with open(suite_report_path) as f:
            csv_reader = csv.DictReader(f)
            for row in csv_reader:
                row = {k.upper(): v for k, v in row.items()}
                if row["STATUS"] not in ("passed", "skipped"):
                    failed_suites.add(row["SUB SUITE"])
        failed_test_labels = ",".join(failed_suites)
        if os.getenv("IS_NIGHTLY_RUN") == "true":
            replay_message = f"To label & retry, run the <https://github.com/uc-cdis/gen3-code-vigil/actions/workflows/nightly_run.yaml|nightly_run workflow> setting TEST_LABELS to `{failed_test_labels}`"
        else:
            replay_message = f"To label & retry, just send the following message:\n `@qa-bot replay-pr {os.getenv('REPO')} {os.getenv('PR_NUM')} {failed_test_labels}`"
        failed_suites_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": replay_message,
            },
        }
        return failed_suites_block
    else:
        return None


def get_test_result_and_metrics():
    allure_summary_path = (
        Path(__file__).parent.parent.parent
        / "allure-report"
        / "widgets"
        / "summary.json"
    )
    if allure_summary_path.exists:
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
        duration = (
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
                "text": f"*Test Metrics*:   :white_check_mark: Passed - {passed}    :x: Failed  - {failed}    :large_yellow_circle: Skipped  - {skipped}    :stopwatch: Run Time - {duration} minutes",
            },
        }
        return (test_result, test_metrics_block)
    else:
        return ("Failed", None)


def generate_slack_report():
    if os.getenv("IS_NIGHTLY_RUN") == "true":
        pr_link = f"https://github.com/{os.getenv('REPO_FN')}/actions/runs/{os.getenv('RUN_ID')}"
        report_link = f"https://qa.planx-pla.net/dashboard/Secure/gen3-ci-reports/nightly-run/{datetime.now().strftime('%Y%m%d')}/index.html"
    else:
        pr_link = (
            f"https://github.com/{os.getenv('REPO_FN')}/pull/{os.getenv('PR_NUM')}"
        )
        report_link = f"https://qa.planx-pla.net/dashboard/Secure/gen3-ci-reports/{os.getenv('REPO')}/{os.getenv('PR_NUM')}/{os.getenv('RUN_NUM')}/{os.getenv('ATTEMPT_NUM')}/index.html"
    slack_report_json = {}
    # Fetch run result and test metrics
    test_result, test_metrics_block = get_test_result_and_metrics()
    test_result_icons = {"Successful": ":tada:", "Failed": ":fire:"}
    slack_report_json["text"] = f"Integration Test Result: {pr_link}"
    slack_report_json["blocks"] = []
    # Header
    header_block = {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "Integration Test Results",
            "emoji": True,
        },
    }
    slack_report_json["blocks"].append(header_block)
    # Run summary
    summary_block = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"{test_result_icons[test_result]} {test_result} run for {pr_link} on :round_pushpin:*{os.getenv('NAMESPACE')}*",
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
                "text": f"*Test Report*: <{report_link}|click here>  _(login to https://qa.planx-pla.net first)_",
            },
        }
        slack_report_json["blocks"].append(report_link_block)
    else:
        logger.info(
            "Allure report was not found. Skipping test metrics block generation."
        )
    # Pod logs url
    if test_result == "Failed" and os.getenv("POD_LOGS_URL"):
        pod_logs_url__block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Pod Logs Archive*: <{os.getenv('POD_LOGS_URL')}|click here>",
            },
        }
        slack_report_json["blocks"].append(pod_logs_url__block)
    else:
        logger.info(
            "Pod logs were not archived. Skipping pod logs url block generation."
        )
    # qa-bot replay command with failed suites labeled in the PR
    if test_result == "Failed":
        failed_suites_block = get_failed_suites()
        if failed_suites_block:
            slack_report_json["blocks"].append(failed_suites_block)

    if os.getenv("IS_NIGHTLY_RUN") == "true":
        slack_report_json["channel"] = "#nightly-builds"
    else:
        slack_report_json["channel"] = os.getenv("SLACK_CHANNEL")
    # DEBUG LOGS
    print(slack_report_json)

    json.dump(slack_report_json, open("slack_report.json", "w"))


if __name__ == "__main__":
    logger.info("Generating slack report ...")
    generate_slack_report()
