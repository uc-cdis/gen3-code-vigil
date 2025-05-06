import json
import os
import subprocess
import time
import uuid

import pytest
import requests
from dotenv import load_dotenv
from utils import logger
from utils.jenkins import JenkinsJob

load_dotenv()
CLOUD_AUTO_BRANCH = os.getenv("CLOUD_AUTO_BRANCH")


def get_portal_config():
    """Fetch portal config from the GUI"""
    res = requests.get(f"{pytest.root_url_portal}/data/config/gitops.json")
    if res.status_code == 200:
        return res.json()
    else:
        raise Exception(
            f"Unable to get portal config: status code {res.status_code} - response {res.text}"
        )


def get_kube_namespace(hostname: str = ""):
    """
    Compute the kubernetes namespace
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        return hostname.split(".")[0]
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        # TODO: Set up the namespace in helm deployment and use it like below. For now just use hostname
        #     cmd = (
        #         "kubectl get configmap manifest-global -o json | jq -r '.data.environment'"
        #     )
        #     result = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
        #     return result.stdout.decode("utf-8")
        return hostname


def get_env_configurations(test_env_namespace: str = ""):
    """
    Fetch configs that require adminvm interaction using jenkins.
    Returns dict { file name: file contents }
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        assert test_env_namespace != ""
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-fetch-configs",
        )
        params = {
            "NAMESPACE": test_env_namespace,
            "CLOUD_AUTO_BRANCH": CLOUD_AUTO_BRANCH,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return {
                    "manifest.json": job.get_artifact_content(
                        build_num, "manifest.json"
                    ),
                }
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        cmd = ["kubectl", "get", "configmap", "manifest-global", "-o", "json"]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            jq_command = ["jq", "-r", ".data"]
            jq_result = subprocess.run(
                jq_command,
                input=result.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if jq_result.returncode == 0:
                return {"manifest.json": '{ "global": ' + jq_result.stdout + "}"}
            else:
                logger.info(f"Error in jq command: {jq_result.stderr}")
        else:
            logger.info(f"Error in kubectl command: {result.stderr}")


def run_gen3_command(
    command: str, test_env_namespace: str = "", roll_all: bool = False
):
    """
    Run gen3 command (e.g., gen3 --help).
    Since this requires adminvm interaction we use jenkins.
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-run-gen3-command",
        )
        params = {
            "NAMESPACE": test_env_namespace,
            "COMMAND": command,
            "CLOUD_AUTO_BRANCH": CLOUD_AUTO_BRANCH,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return job.get_build_result(build_num)
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        pass


def run_gen3_job(
    job_name: str,
    cmd_line_params: str = "",
    test_env_namespace: str = "",
    roll_all: bool = False,
):
    """
    Run gen3 job (e.g., metadata-aggregate-sync).
    Since this requires adminvm interaction we use jenkins.
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-run-gen3-job",
        )
        params = {
            "NAMESPACE": test_env_namespace,
            "JOB_NAME": job_name,
            "CMD_LINE_PARAMS": cmd_line_params,
            "GEN3_ROLL_ALL": roll_all,
            "CLOUD_AUTO_BRANCH": CLOUD_AUTO_BRANCH,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return job.get_build_result(build_num)
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        # job_pod = f"{job_name}-{uuid.uuid4()}"
        if job_name == "etl":
            job_name = "etl-cronjob"
        cmd = ["kubectl", "delete", "job", job_name]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if not result.returncode == 0:
            logger.info(
                f"Unable to delete {job_name} - {result.stderr.decode('utf-8')}"
            )
        cmd = ["kubectl", "create", "job", f"--from=cronjob/{job_name}", job_name]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            logger.info(f"{job_name} job triggered - {result.stdout.decode('utf-8')}")
        else:
            raise Exception(
                f"{job_name} failed to start - {result.stderr.decode('utf-8')}"
            )


def check_job_pod(
    job_name: str,
    label_name: str,
    test_env_namespace: str = "",
    expect_failure: bool = False,
):
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-check-kube-job-pod",
        )
        params = {
            "NAMESPACE": test_env_namespace,
            "JOB_NAME": job_name,
            "LABEL_NAME": label_name,
            "EXPECT_FAILURE": expect_failure,
            "CLOUD_AUTO_BRANCH": CLOUD_AUTO_BRANCH,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return {"logs.txt": job.get_artifact_content(build_num, "logs.txt")}
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        # Wait for the job pod to start
        cmd = [
            "kubectl",
            "get",
            "pods",
            f"--selector=job-name={job_name}",
            "-o",
            "jsonpath='{.items[0].status.phase}'",
        ]
        i = 0
        job_started = False
        for i in range(6):
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            if result.stdout.replace("'", "") in [
                "Running",
                "Succeeded",
                "Failed",
                "Completed",
            ]:
                job_started = True
                break
            else:
                time.sleep(10)
        if job_started is False:
            raise Exception(f"Pod failed to start for job {job_name}")

        # Wait for the job to complete
        cmd = [
            "kubectl",
            "get",
            "job",
            job_name,
            "-o",
            "jsonpath='{.status.conditions[?(@.type==\"Complete\")].status}'",
        ]
        job_completed = False
        for i in range(40):
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            if result.stdout.replace("'", "") == "True":
                job_completed = True
                break
            else:
                time.sleep(30)
        if job_completed is False:
            raise Exception(f"Job {job_name} failed to complete in 20 minutes")


def create_access_token(service, expired, username, test_env_namespace: str = ""):
    """
    Roll a give service pod
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-create-access-token",
        )
        if expired:
            expiration = 1
        else:
            expiration = 300  # 5 min
        params = {
            "SERVICE": service,
            "EXPIRATION": expiration,
            "USERNAME": username,
            "NAMESPACE": test_env_namespace,
            "CLOUD_AUTO_BRANCH": CLOUD_AUTO_BRANCH,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num, max_duration=300)
            if status == "Completed":
                if expired:
                    time.sleep(expiration)
                return job.get_artifact_content(build_num, "access_token.txt")
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        # Get the pod name for fence app
        cmd = ["kubectl", "get", "pods", "-l", "app=fence"]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            fence_pod_name = result.stdout.splitlines()[-1].split()[0]
        else:
            raise Exception("Unable to retrieve fence-deployment pod")
        cmd = [
            "kubectl",
            "exec",
            "-i",
            fence_pod_name,
            "--",
            "fence-create",
            "token-create",
            "--scopes",
            "openid,user,fence,data,credentials,google_service_account,google_credentials",
            "--type",
            "access_token",
            "--exp",
            expired,
            "--username",
            username,
        ]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            raise Exception("Unable to get expired access_token")
