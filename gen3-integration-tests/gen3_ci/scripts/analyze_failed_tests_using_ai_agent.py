import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from utils import logger

load_dotenv()


def setup_helm_chart(service):
    cmd = [
        "helm",
        "install",
        service,
        f"gen3_ci/{service}",
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
            f"Unable to install {service}. Error: {helm_install_result.stderr.strip()}"
        )

    cmd = [
        "kubectl",
        "wait",
        "--for=condition=ready",
        "pod",
        "-l",
        f"app={service}",
        "--timeout=10m",
        "-n",
        os.getenv("NAMESPACE"),
    ]

    service_pod_ready_result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if not service_pod_ready_result.returncode == 0:
        raise Exception(
            f"{service} pod hasn't started yet. Error: {service_pod_ready_result.stderr.strip()}"
        )


def wait_for_port(host="localhost", port=11434, timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(1)
    raise TimeoutError("Port-forward did not become ready")


def setup_port_forwarding(service):
    cmd = [
        "kubectl",
        "port-forward",
        f"svc/{service}",
        "11434:11434",
        "-n",
        os.getenv("NAMESPACE"),
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    wait_for_port("localhost", 11434, timeout=60)
    return process


def uninstall_helm_chart(service):
    cmd = [
        "helm",
        "uninstall",
        service,
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
            f"Unable to uninstall {service}. Error: {helm_install_result.stderr.strip()}"
        )


def validate_ollama_model():
    response = requests.get("http://localhost:11434/api/tags")
    logger.info(response.json())
    return response.json()


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
    messages = [
        {"role": "system", "content": debug_prompt},
        {"role": "user", "content": "analyse the errors from this logfile"},
    ]
    payload = {"model": "qwen3.5:2b", "messages": messages, "temperature": 0}
    headers = {"Content-Type": "application/json"}
    url = "http://localhost:11434/v1/chat/completions"
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code != 200:
        logger.info(f"API call failed. Response: {response.text}")
    return response.content


def analyze_env_setup_failure_using_kubectl_ai() -> str:
    cmd = [
        "kubectl",
        "-n",
        os.getenv("NAMESPACE"),
        "get",
        "pods",
        "-l",
        "app=kubectl-ai",
        "-o",
        "jsonpath='{.items[0].metadata.name}'",
    ]
    kubeclt_ai_pod_result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=600,
    )
    if not kubeclt_ai_pod_result.returncode == 0:
        raise Exception(
            f"Failed to get kubectl-ai pod. Error: {kubeclt_ai_pod_result.stderr.strip()}"
        )
    kubeclt_ai_pod_name = kubeclt_ai_pod_result.stdout.strip().replace("'", "")
    kubectl_ai_cmd = [
        "kubectl",
        "-n",
        os.getenv("NAMESPACE"),
        "exec",
        kubeclt_ai_pod_name,
        "--",
        "kubectl-ai",
        "--llm-provider",
        "ollama",
        "--model",
        "qwen3.5:2b",
        "--skip-permissions",
        f'Check if any pods are not healthy on {os.getenv("NAMESPACE")} namespace and anaylyze the logs',
    ]
    logger.info(kubectl_ai_cmd)
    kubectl_ai_result = subprocess.run(
        kubectl_ai_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=600,
    )
    if not kubectl_ai_result.returncode == 0:
        raise Exception(
            f"kubectl-ai command output. Error: {kubectl_ai_result.stdout.strip()}"
            f"kubectl-ai command failed. Error: {kubectl_ai_result.stderr.strip()}"
        )
    return kubectl_ai_result.stdout.strip()


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
        messages = [
            {"role": "system", "content": debug_prompt},
            {"role": "user", "content": "analyse the failed tests"},
        ]
        payload = {"model": "qwen3.5:2b", "messages": messages, "temperature": 0}
        headers = {"Content-Type": "application/json"}
        url = "http://localhost:11434/v1/chat/completions"
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            logger.info(f"API call failed. Response: {response.text}")
        return response.content
    logger.info("No allure report folder found")
    return analyze_env_setup_failure()


def run_test_failure_analysis():
    if os.getenv("PR_ERROR_MSG") == "Failed to Prepare CI environment":
        try:
            setup_helm_chart(service="kubectl-ai")
            process = setup_port_forwarding(service="kubectl-ai")
            assert "qwen3.5:2b" in str(validate_ollama_model())
            # response = analyze_env_setup_failure()
            response = analyze_env_setup_failure_using_kubectl_ai()
        except Exception as e:
            logger.info(
                f"Failed to run analyze_env_setup_failure_using_kubectl_ai: {e}"
            )
        finally:
            uninstall_helm_chart(service="kubectl-ai")
    else:
        try:
            setup_helm_chart(service="ollama")
            process = setup_port_forwarding(service="ollama")
            assert "gemma4:e4b" in str(validate_ollama_model())
            response = analyze_failed_tests()
        except Exception as e:
            logger.info(f"Failed to run analyze_failed_tests: {e}")
        finally:
            uninstall_helm_chart(service="ollama")
    if response is None:
        return "No logs found to analyze"
    data = json.loads(response.decode("utf-8"))
    reasoning = data["choices"][0]["message"].get("content")
    return reasoning, process


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
