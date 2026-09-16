import json
import os
import re
import shlex
import socket
import subprocess
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from utils import logger

load_dotenv()


def run_analysis(execute_command) -> str:
    logger.info("Running Analysis on Failure-analysis pod")
    cmd = [
        "kubectl",
        "-n",
        "qabot",
        "get",
        "pods",
        "-l",
        "app=failure-analysis",
    ]
    failure_analysis_pod_result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=600,
    )
    if not failure_analysis_pod_result.returncode == 0:
        logger.info(
            f"Failed to get failure-analysis pod. Error: {failure_analysis_pod_result.stderr.strip()}"
        )
        raise Exception(
            f"Failed to get failure-analysis pod. Error: {failure_analysis_pod_result.stderr.strip()}"
        )
    failure_analysis_pod_name = failure_analysis_pod_result.stdout.splitlines()[
        -1
    ].split()[0]
    failure_analysis_cmd = (
        f"kubectl -n qabot exec {failure_analysis_pod_name} -- {execute_command}"
    )
    failure_analysis_result = subprocess.run(
        failure_analysis_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=600,
        shell=True,
    )
    if not failure_analysis_result.returncode == 0:
        logger.info(
            f"failure-analysis command failed. Error: {failure_analysis_result.stderr.strip()}"
        )
        return f"failure-analysis command failed. Error: {failure_analysis_result.stderr.strip()}"
    report_cmd = [
        "kubectl",
        "-n",
        "qabot",
        "exec",
        failure_analysis_pod_name,
        "--",
        "cat",
        f"/tmp/summary-{os.getenv("NAMESPACE")}.txt",
    ]
    report_result = subprocess.run(
        report_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=600,
    )
    if not report_result.returncode == 0:
        logger.info(f"report command failed. Error: {report_result.stderr.strip()}")
        raise Exception(f"report command failed. Error: {report_result.stderr.strip()}")
    return report_result.stdout.strip()


def analyze_env_setup_failure_using_kubectl_ai() -> str:
    kubectl_prompt = f'"List unhealthy pods in the {os.getenv("NAMESPACE")} namespace (CrashLoopBackOff, Error, Pending). For each pod, inspect only relevant events and the last 50 log lines. Summarize the root cause briefly. Write a concise report to /tmp/summary-{os.getenv("NAMESPACE")}.txt."'
    execute_command = f"kubectl-ai --llm-provider=openai --model=Qwen/Qwen3.8-27B-FP8 --skip-permissions --quiet {kubectl_prompt}"
    return run_analysis(execute_command)


def analyze_env_setup_failure() -> str:
    """Check env setup failure and analyze the error"""
    logger.info("Checking logs/gh_action_logs.txt")
    log_file_path = "logs/gh_action_logs.txt"
    if not os.path.exists(log_file_path):
        logger.info(f"{log_file_path} path doesn't exists")
        return None
    with open(log_file_path, "r") as f:
        logfile_content = f.read().split("Upload reports to S3", 1)[0]

    debug_prompt = f"""
    All output MUST be in English. Do not use any other language.

    You are a senior DevOps engineer.

    Find all errors and exceptions in the logfile content and analyze them.

    Return output sctrictly in this format for each error:

    Possible Root cause:
    <one clear sentence>
    Potential Fix:
    <actionable remediation steps>

    Start with an "Executive Summary" (2–3 sentences).
    After that, keep all explanations very brief—summary style only, no long paragraphs.

    Log:
    {logfile_content}
    """
    messages = [{"role": "system", "content": debug_prompt}]
    payload = {"model": "Qwen/Qwen3.8-27B-FP8", "messages": messages, "temperature": 0}
    payload_json = json.dumps(payload)
    execute_command = "sh -c " + shlex.quote(
        f"curl -X POST "
        f'-H "Content-Type: application/json" '
        f"-d {shlex.quote(payload_json)} "
        f'"$OPENAI_ENDPOINT/chat/completions" '
        f"> /tmp/summary-{os.getenv('NAMESPACE')}.txt"
    )
    response = run_analysis(execute_command)
    data = json.load(response)
    reasoning = data["choices"][0]["message"].get("content")
    return reasoning


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
        All output MUST be in English. Do not use any other language.

        You are a senior DevOps engineer.

        Analyze each status message below.

        Return output sctrictly in this format for each test failure:

            Test case: <test case name>
            Possible Root cause:
            <one clear sentence>
            Potential Fix:
            <actionable remediation steps>

        Keep all explanations very brief—just a summary, no long paragraphs.

        Status Trace:
        {failed_tests}
        """
        messages = [{"role": "system", "content": debug_prompt}]
        payload = {
            "model": "Qwen/Qwen3.8-27B-FP8",
            "messages": messages,
            "temperature": 0,
        }
        payload_json = json.dumps(payload)
        execute_command = "sh -c " + shlex.quote(
            f"curl -X POST "
            f'-H "Content-Type: application/json" '
            f"-d {shlex.quote(payload_json)} "
            f'"$OPENAI_ENDPOINT/chat/completions" '
            f"> /tmp/summary-{os.getenv('NAMESPACE')}.txt"
        )
        response = run_analysis(execute_command)
        logger.info(f"Response: {response}")
        data = json.loads(response)
        reasoning = data["choices"][0]["message"].get("content")
        return reasoning
    logger.info("No allure report folder found")
    return analyze_env_setup_failure()


def run_test_failure_analysis():
    if os.getenv("PR_ERROR_MSG") and "Failed to Prepare CI environment" in os.getenv(
        "PR_ERROR_MSG"
    ):
        try:
            response = analyze_env_setup_failure_using_kubectl_ai()
        except Exception as e:
            logger.info(
                f"Failed to run analyze_env_setup_failure_using_kubectl_ai: {e}"
            )
    else:
        try:
            response = analyze_failed_tests()
        except Exception as e:
            logger.info(f"Failed to run analyze_failed_tests: {e}")
    if response is None:
        return "No logs found to analyze"
    return response, process


def generate_slack_report():
    if os.getenv("IS_NIGHTLY_RUN") == "true":
        failure_analysis_link = f"https://allure.ci.planx-pla.net/nightly-run-{os.getenv('CI_ENV')}/{datetime.now().strftime('%Y%m%d')}/{os.getenv('RUN_NUM')}/{os.getenv('ATTEMPT_NUM')}/failure_analysis.txt"
    else:
        failure_analysis_link = f"https://allure.ci.planx-pla.net/{os.getenv('REPO')}/{os.getenv('PR_NUM')}/{os.getenv('RUN_NUM')}/{os.getenv('ATTEMPT_NUM')}/failure_analysis.txt"
    slack_report_json = {}
    slack_report_json["blocks"] = []
    failure_analysis_path = (
        Path(__file__).parent.parent.parent / "logs" / "failure_analysis.txt"
    )
    if failure_analysis_path.exists():
        failure_analysis_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Failure Analysis*: <{failure_analysis_link}|click here>",
            },
        }
        slack_report_json["blocks"].append(failure_analysis_block)
    else:
        logger.info("No failure_analysis.txt file found")
        return
    if os.getenv("IS_NIGHTLY_RUN") == "true":
        slack_report_json["channel"] = "#nightly-builds"
    else:
        slack_report_json["channel"] = os.getenv("SLACK_CHANNEL")
    slack_report_json["thread_ts"] = os.getenv("THREAD_TS")
    logger.info(slack_report_json)
    json.dump(slack_report_json, open("test_analysis_slack_report.json", "w"))


if __name__ == "__main__":
    process = None
    try:
        response, process = run_test_failure_analysis()
        with open("logs/failure_analysis.txt", "w") as f:
            f.write(response)
        generate_slack_report()
    except Exception as e:
        logger.info(f"Failed to run inference: {e}")
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait()
