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
    res = requests.get(f"{pytest.root_url}/data/config/gitops.json")
    if res.status_code == 200:
        return res.json()
    else:
        return None


def get_portal_config_from_kube_secrets(test_env_namespace):
    """
    Fetch portal config from kubernetes secrets.
    Since this requires adminvm interaction we use jenkins.
    """
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "ci-only-fetch-portal-config",
    )
    params = {"TARGET_ENVIRONMENT": test_env_namespace}
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num)
        if status == "Completed":
            return job.get_artifact_content(build_num, "gitops.json")
        else:
            logger.error("Build timed out. Consider increasing max_duration")
            res = job.terminate_build(build_num)
            if res == "SUCCESS":
                logger.info(f"Terminated {build_num} of job {job.job_name}")
            else:
                logger.error(f"Failed to terminate {build_num} of job {job.job_name}")
            return None
    else:
        logger.error("Build number not found")
        return None


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
        "TARGET_ENVIRONMENT": test_env_namespace,
        "JOB_NAME": job_name,
        "GEN3_ROLL_ALL": roll_all,
    }
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num, max_duration=600)
        if status == "Completed":
            return job.get_build_result(build_num)
        else:
            logger.error("Build timed out. Consider increasing max_duration")
            res = job.terminate_build(build_num)
            if res == "SUCCESS":
                logger.info(f"Terminated {build_num} of job {job.job_name}")
            else:
                logger.error(f"Failed to terminate {build_num} of job {job.job_name}")
            return None
    else:
        logger.error("Build number not found")
        return None
