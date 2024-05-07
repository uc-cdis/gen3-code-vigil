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


def get_admin_vm_configurations(test_env_namespace: str):
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


def run_gen3_job(test_env_namespace: str, job_name: str, roll_all: bool = False):
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
        status = job.wait_for_build_completion(build_num)
        if status == "Completed":
            return job.get_build_result(build_num)
        else:
            job.terminate_build(build_num)
            raise Exception("Build timed out. Consider increasing max_duration")
    else:
        raise Exception("Build number not found")


def kube_setup_service(test_env_namespace, servicename):
    """
    Runs jenkins job to kube setup service
    """
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "kube-setup-service",
    )
    params = {
        "SERVICENAME": servicename,
        "NAMESPACE": test_env_namespace,
    }
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num)
        if status == "Completed":
            return True
        else:
            job.terminate_build(build_num)
            raise Exception("Build timed out. Consider increasing max_duration")
    else:
        raise Exception("Build number not found")


def generate_test_data(
    test_env_namespace: str,
    max_examples: int,
):
    """
    Runs jenkins job to generate test data
    Since this requires adminvm interaction we use jenkins
    """
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "generate-test-data",
    )
    params = {
        "NAMESPACE": test_env_namespace,
        "MAX_EXAMPLES": max_examples,
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


def create_fence_client(
    test_env_namespace: str,
    client_name: str,
    user_name: str,
    client_type: str,
    arborist_policies: str = None,
    expires_in: str = "",
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
        status = job.wait_for_build_completion(build_num)
        if status == "Completed":
            return {
                "client_creds.txt": job.get_artifact_content(
                    build_num, "client_creds.txt"
                ),
            }
        else:
            job.terminate_build(build_num)
            raise Exception("Build timed out. Consider increasing max_duration")
    else:
        raise Exception("Build number not found")


def delete_fence_client(test_env_namespace: str, client_name: str):
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
        status = job.wait_for_build_completion(build_num)
        if status == "Completed":
            return job.get_build_result(build_num)
        else:
            job.terminate_build(build_num)
            raise Exception("Build timed out. Consider increasing max_duration")
    else:
        raise Exception("Build number not found")


def revoke_arborist_policy(test_env_namespace: str, username: str, policy: str):
    """
    Runs jenkins job to revoke arborist policy
    Since jenkins job is faster way without too much configuration changes
    """
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "revoke-arborist-policy",
    )
    params = {
        "NAMESPACE": test_env_namespace,
        "USERNAME": username,
        "POLICY": policy,
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


def update_audit_service_logging(test_env_namespace: str, audit_logging: str):
    """
    Runs jenkins job to enable/disable audit logging
    """
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "audit-service-logging",
    )
    params = {
        "AUDIT_LOGGING": audit_logging,
        "NAMESPACE": test_env_namespace,
    }
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num)
        if status == "Completed":
            return True
        else:
            job.terminate_build(build_num)
            raise Exception("Build timed out. Consider increasing max_duration")
    else:
        raise Exception("Build number not found")


def mutate_manifest_for_guppy_test(test_env_namespace: str):
    """
    Runs jenkins job to point guppy to pre-defined Canine ETL'ed data
    """
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "mutate-manifest-for-guppy-test",
    )
    params = {
        "NAMESPACE": test_env_namespace,
    }
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num)
        if status == "Completed":
            return True
        else:
            job.terminate_build(build_num)
            raise Exception("Build timed out. Consider increasing max_duration")
    else:
        raise Exception("Build number not found")


def clean_up_indices(test_env_namespace: str):
    """
    Runs jenkins job to clean up indices before running the ETL tests
    """
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "clean-up-indices",
    )
    params = {"NAMESPACE": test_env_namespace}
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num, max_duration=300)
        if status == "Completed":
            return True
        else:
            job.terminate_build(build_num)
            raise Exception("Build timed out. Consider increasing max_duration")
    else:
        raise Exception("Build number not found")


def check_indices_after_etl(test_env_namespace: str):
    """
    Runs jenkins job to clean up indices before running the ETL tests
    """
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "check_indices_after_etl",
    )
    params = {"NAMESPACE": test_env_namespace}
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num, max_duration=300)
        if status == "Completed":
            return True
        else:
            job.terminate_build(build_num)
            raise Exception("Build timed out. Consider increasing max_duration")
    else:
        raise Exception("Build number not found")
