import os
import pytest
import requests

from dotenv import load_dotenv
from cdislogging import get_logger

from utils.jenkins import JenkinsJob

load_dotenv()

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def get_portal_config(test_env_namespace):
    """Fetch portal config from the GUI"""
    if "heal" in pytest.tested_env:
        res = requests.get(f"{pytest.root_url}/portal/data/config/gitops.json")
    else:
        res = requests.get(f"{pytest.root_url}/data/config/gitops.json")
    if res.status_code == 200:
        return res.json()
    else:
        raise Exception(
            f"Unable to get portal config: status code {res.status_code} - response {res.text}"
        )


def get_admin_vm_configurations(test_env_namespace):
    """
    Fetch configs that require adminvm interaction using jenkins.
    Returns dict { file name: file contents }
    """
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "ci-only-fetch-configs",
    )
    params = {"NAMESPACE": test_env_namespace}
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num)
        if status == "Completed":
            return {
                "manifest.json": job.get_artifact_content(build_num, "manifest.json"),
            }
        else:
            job.terminate_build(build_num)
            raise Exception("Build timed out. Consider increasing max_duration")
    else:
        raise Exception("Build number not found")


def run_gen3_job(test_env_namespace, job_name, roll_all=False):
    """
    Run gen3 job (e.g., metadata-aggregate-sync).
    Since this requires adminvm interaction we use jenkins.
    """
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "ci-only-run-gen3-job",
    )
    params = {
        "NAMESPACE": test_env_namespace,
        "JOB_NAME": job_name,
        "GEN3_ROLL_ALL": roll_all,
    }
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num, max_duration=600)
        if status == "Completed":
            return job.get_build_result(build_num)
        else:
            job.terminate_build(build_num)
            raise Exception("Build timed out. Consider increasing max_duration")
    else:
      raise Exception("Build number not found")


def create_fence_client(
    test_env_namespace,
    client_name,
    user_name,
    client_type,
    arborist_policies,
    expires_in,
):
    """
    Runs jenkins job to create a fence client
    Since this requires adminvm interaction we use jenkins.
    """
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "fence-create-client",
    )
    params = {
        "CLIENT_NAME": client_name,
        "USER_NAME": user_name,
        "CLIENT_TYPE": client_type,
        "ARBORIST_POLICIES": arborist_policies,
        "EXPIRES_IN": expires_in,
        "NAMESPACE": test_env_namespace,
    }
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num, max_duration=600)
        if status == "Completed":
            return {
                "client_creds.json": job.get_artifact_content(
                    build_num, "client_creds.json"
                ),
            }
        else:
            job.terminate_build(build_num)
            raise Exception("Build timed out. Consider increasing max_duration")
    else:
        raise Exception("Build number not found")


def delete_fence_client(test_env_namespace, client_name):
    """
    Runs jenkins job to delete client
    Since this requires adminvm interaction we use jenkins.
    """
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "fence-delete-client",
    )
    params = {
        "CLIENT_NAME": client_name,
        "NAMESPACE": test_env_namespace,
    }
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num, max_duration=600)
        if status == "Completed":
            return job.get_build_result(build_num)
        else:
            job.terminate_build(build_num)
            raise Exception("Build timed out. Consider increasing max_duration")
    else:
        raise Exception("Build number not found")