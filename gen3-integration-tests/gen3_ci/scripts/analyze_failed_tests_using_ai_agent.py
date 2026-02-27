import json
import os
import re
import subprocess
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from utils import logger

load_dotenv()


def setup_ollama_helm_chart():
    cmd = [
        "helm",
        "install",
        "ollama",
        "gen3_ci/ollama",
        "-n",
        os.getenv("NAMESPACE"),
    ]

    helm_install_result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not helm_install_result.returncode == 0:
        raise Exception(
            f"Unable to install ollama. Error: {helm_install_result.stderr.strip()}"
        )

    cmd = [
        "kubectl",
        "wait",
        "--for=condition=ready",
        "pod",
        "-l",
        "app=ollama",
        "--timeout=5m",
        "-n",
        os.getenv("NAMESPACE"),
    ]

    ollama_pod_ready_result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not ollama_pod_ready_result.returncode == 0:
        raise Exception(
            f"Unable to install ollama. Error: {ollama_pod_ready_result.stderr.strip()}"
        )


def setup_port_forwarding():
    cmd = [
        "kubectl",
        "port-forward",
        "svc/ollama",
        "11434:11434",
        "-n",
        os.getenv("NAMESPACE"),
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return process


def uninstall_ollama_helm_chart():
    cmd = [
        "helm",
        "uninstall",
        "ollama",
        "-n",
        os.getenv("NAMESPACE"),
    ]

    helm_install_result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not helm_install_result.returncode == 0:
        raise Exception(
            f"Unable to uninstall ollama. Error: {helm_install_result.stderr.strip()}"
        )


def validate_ollama_model():
    # Need to find fix for this sleep - the ollama model isnt available immediately after pod is up
    time.sleep(30)
    response = requests.get("http://localhost:11434/api/tags")
    logger.info(response.json())
    return response.json()


def analyze_env_setup_failure() -> str:
    """Check env setup failure and analyze the error"""
    logger.info("Checking logs/gh_action_logs.txt")
    with open("logs/gh_action_logs.txt", "r") as f:
        logfile_content = f.read()
    pattern = re.compile(r"\b(error|failed|exception|traceback)\b", re.IGNORECASE)

    error_lines = "\n".join(
        [line for line in logfile_content.splitlines() if pattern.search(line)]
    )
    debug_prompt = f"""
    You are a senior DevOps engineer.

    Analyze the log snippet below.

    Return output sctrictly in this format for each error:

    Root cause:
    <one clear sentence>

    Fix:
    <actionable remediation steps>

    Keep all explanations very brief—just a summary, no long paragraphs.

    Log:
    {error_lines}
    """
    messages = [
        {"role": "system", "content": debug_prompt},
        {"role": "user", "content": "analyse the errors"},
    ]
    payload = {"model": "gemma3:12b", "messages": messages, "temperature": 0}
    headers = {"Content-Type": "application/json"}
    url = "http://localhost:11434/v1/chat/completions"
    response = requests.post(url, json=payload, headers=headers)
    return response.content


def analyze_failed_tests() -> str:
    """Analyze the failed tests and provide fixes"""
    if Path("rerun-allure-report").exists():
        report_dir = Path("rerun-allure-report/data/test-cases")
    elif Path("allure-report/data/test-cases").exists():
        report_dir = Path("allure-report/data/test-cases")
    else:
        report_dir = None

    if report_dir:
        logger.info(f"Looking into {report_dir} folder")
        failed_tests = {"failed_tests": []}

        for case_file in report_dir.glob("*.json"):
            with case_file.open() as f:
                case = json.load(f)
            if case.get("status") in ["failed", "broken"]:
                failed_tests["failed_tests"].append(
                    {
                        "name": case.get("name"),
                        "statusMessage": case.get("statusMessage"),
                    },
                )
        debug_prompt = f"""
        You are a senior DevOps engineer.

        Analyze each status message below.

        Return output sctrictly in this format for each test failure:

            Test case: <test case name>

            Root cause:
            <one clear sentence>

            Fix:
            <actionable remediation steps>

        Keep all explanations very brief—just a summary, no long paragraphs.

        Status Trace:
        {failed_tests}
        """
        messages = [
            {"role": "system", "content": debug_prompt},
            {"role": "user", "content": "analyse the failed tests"},
        ]
        payload = {"model": "gemma3:12b", "messages": messages, "temperature": 0}
        headers = {"Content-Type": "application/json"}
        url = "http://localhost:11434/v1/chat/completions"
        response = requests.post(url, json=payload, headers=headers)
        return response.content
    else:
        return "No reports found"


def run_test_failure_analysis():
    if os.getenv("PR_ERROR_MSG") == "Failed to Prepare CI environment":
        response = analyze_env_setup_failure()
    else:
        response = analyze_failed_tests()
    data = json.loads(response.decode("utf-8"))
    reasoning = data["choices"][0]["message"].get("content")
    logger.info(reasoning)
    return reasoning


def generate_slack_report(response):
    slack_report_json = {}
    slack_report_json["text"] = "Failed Test Analysis"
    slack_report_json["blocks"] = []
    header_block = {
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "Failed Test Analysis",
            "emoji": True,
        },
    }
    slack_report_json["blocks"].append(header_block)
    summary_block = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": response,
        },
    }
    slack_report_json["blocks"].append(summary_block)
    if os.getenv("IS_NIGHTLY_RUN") == "true":
        slack_report_json["channel"] = "#nightly-builds"
    else:
        slack_report_json["channel"] = os.getenv("SLACK_CHANNEL")
    slack_report_json["thread_ts"] = os.getenv("THREAD_TS")
    json.dump(slack_report_json, open("test_analysis_slack_report.json", "w"))


if __name__ == "__main__":
    process = None
    try:
        setup_ollama_helm_chart()
        process = setup_port_forwarding()
        time.sleep(10)
        assert "gemma3:12b" in str(validate_ollama_model())
        response = run_test_failure_analysis()
        generate_slack_report(response)
    except Exception as e:
        logger.info(f"Failed to run inference: {e}")
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait()
        uninstall_ollama_helm_chart()
