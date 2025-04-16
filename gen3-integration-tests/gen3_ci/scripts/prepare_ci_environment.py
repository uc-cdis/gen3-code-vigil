import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv
from utils import HELM_SCRIPTS_PATH_OBJECT, TEST_DATA_PATH_OBJECT, logger, test_setup
from utils.jenkins import JenkinsJob

load_dotenv()
CLOUD_AUTO_BRANCH = os.getenv("CLOUD_AUTO_BRANCH")


def wait_for_quay_build(repo, tag):
    """
    Wait for the branch image to be ready for testing.
    Used in service PRs.
    """
    repo_image_status = {}
    quay_url_org = "https://quay.io/api/v1/repository/cdis"
    commit_time = datetime.strptime(os.getenv("COMMIT_TIME"), "%Y-%m-%dT%H:%M:%SZ")
    max_tries = 30  # Minutes to wait for image
    found = False
    i = 0
    repo_list = repo.split(",")
    logger.info(f"Repo - {repo}, image - {tag}")
    while not found and i < max_tries:
        for repo_item in repo_list:
            logger.info(f"Waiting for image {repo_item}:{tag} to be built in quay")
            res = requests.get(f"{quay_url_org}/{repo_item}/tag")
            if res.status_code == 200:
                branch_images = [x for x in res.json()["tags"] if x["name"] == tag]
                if len(branch_images) >= 1:
                    image = branch_images[0]
                    image_time = datetime.utcfromtimestamp(image["start_ts"])
                    print(image_time)
                    if image_time > commit_time:
                        repo_image_status[repo_item] = True
                    else:
                        repo_image_status[repo_item] = False
            else:
                repo_image_status[repo_item] = False
        i += 1
        time.sleep(60)
        found = all(repo_image_status.values())
    if found:
        return "success"
    if not found:
        logger.error(f"Image with tag {tag} was not found in repo {repo}")
        return "failure"


def setup_env_for_helm(arguments):
    file_path = HELM_SCRIPTS_PATH_OBJECT / "env_setup.sh"
    logger.info(f"File path: {file_path}")
    logger.info(f"Argument: {arguments}")
    result = subprocess.run([file_path] + arguments, capture_output=True, text=True)
    if result.returncode == 0:
        logger.info("Script executed successfully. Output:")
        logger.info(result.stdout)
        return "SUCCESS"
    else:
        logger.info("Script execution failed. Error:")
        logger.info(result.stderr)
        return "failure"


def modify_env_for_service_pr(namespace, service, tag):
    """
    Change the image tag for the service under test in the test env's manifest
    Roll the environment
    Run usersync
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-modify-env-for-service-pr",
        )
        params = {
            "NAMESPACE": namespace,
            "SERVICE": service,
            "VERSION": tag,
            "CLOUD_AUTO_BRANCH": CLOUD_AUTO_BRANCH,
        }
        build_num = job.build_job(params)
        if build_num:
            env_file = os.getenv("GITHUB_ENV")
            with open(env_file, "a") as myfile:
                myfile.write(f"PREPARE_CI_ENV_JOB_INFO={job.job_name}|{build_num}\n")
            status = job.wait_for_build_completion(build_num, max_duration=5400)
            if status == "Completed":
                return job.get_build_result(build_num)
            else:
                logger.error("Build timed out. Consider increasing max_duration")
                job.terminate_build(build_num)
                return "failure"
        else:
            logger.error("Build number not found")
            return "failure"
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        helm_branch = os.getenv("HELM_BRANCH")
        arguments = [namespace, "service-env-setup", helm_branch, service, tag]
        return setup_env_for_helm(arguments)


def modify_env_for_manifest_pr(namespace, updated_folder, repo):
    """
    Change the image tags for the services under test in the test env's manifest
    Copy the required files like gitops.json, etlmapping.yaml, etc
    Roll the environment
    Run usersync
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-modify-env-for-manifest-pr",
        )
        params = {
            "NAMESPACE": namespace,
            "CLOUD_AUTO_BRANCH": CLOUD_AUTO_BRANCH,
            "UPDATED_FOLDER": updated_folder,
            "TARGET_REPO": repo,
            "TARGET_BRANCH": os.getenv("BRANCH"),
        }
        build_num = job.build_job(params)
        if build_num:
            env_file = os.getenv("GITHUB_ENV")
            with open(env_file, "a") as myfile:
                myfile.write(f"PREPARE_CI_ENV_JOB_INFO={job.job_name}|{build_num}\n")
            status = job.wait_for_build_completion(build_num, max_duration=5400)
            if status == "Completed":
                return job.get_build_result(build_num)
            else:
                logger.error("Build timed out. Consider increasing max_duration")
                job.terminate_build(build_num)
                return "failure"
        else:
            logger.error("Build number not found")
            return "failure"
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        helm_branch = os.getenv("HELM_BRANCH")
        arguments = [
            namespace,
            "manifest-env-setup",
            helm_branch,
            namespace,
            updated_folder,
        ]
        return setup_env_for_helm(arguments)


def modify_env_for_test_repo_pr(namespace):
    """
    We can use the test env's manifest as-is (all services point to master branch)
    Roll the environment
    Run usersync
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-modify-env-for-test-repo-pr",
        )
        params = {
            "NAMESPACE": namespace,
            "CLOUD_AUTO_BRANCH": CLOUD_AUTO_BRANCH,
        }
        build_num = job.build_job(params)
        if build_num:
            env_file = os.getenv("GITHUB_ENV")
            with open(env_file, "a") as myfile:
                myfile.write(f"PREPARE_CI_ENV_JOB_INFO={job.job_name}|{build_num}\n")
            status = job.wait_for_build_completion(build_num, max_duration=5400)
            if status == "Completed":
                res = job.get_build_result(build_num)
                logger.info(
                    f"ci-only-modify-env-for-test-repo-pr job's build {build_num} completed \
                    with status {res}"
                )
                return res
            else:
                logger.error("Build timed out. Consider increasing max_duration")
                job.terminate_build(build_num)
                return "failure"
        else:
            logger.error("Build number not found")
            return "failure"
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        helm_branch = os.getenv("HELM_BRANCH")
        arguments = [namespace, "test-env-setup", helm_branch]
        return setup_env_for_helm(arguments)


def generate_api_keys_for_test_users(namespace):
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        # Accounts used for testing
        test_users = test_setup.get_users()
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-generate-api-keys",
        )
        params = {
            "NAMESPACE": namespace,
            "CLOUD_AUTO_BRANCH": CLOUD_AUTO_BRANCH,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                res = job.get_build_result(build_num)
                if res.lower() == "success":
                    for user in test_users:
                        api_key = json.loads(
                            job.get_artifact_content(
                                build_num, f"{namespace}_{user}.json"
                            )
                        )
                        with open(
                            Path.home() / ".gen3" / f"{namespace}_{user}.json", "w+"
                        ) as key_file:
                            json.dump(api_key, key_file)
                else:
                    raise Exception(
                        "Generation of API keys failed, please check job logs for details"
                    )
            else:
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
        return "SUCCESS"
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        cmd = [
            "bash",
            (HELM_SCRIPTS_PATH_OBJECT / "generate_api_keys.sh"),
            (TEST_DATA_PATH_OBJECT / "test_setup" / "users.csv"),
            pytest.hostname,
        ]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip().replace("'", "")
        else:
            raise Exception(f"Got error: {result.stderr}")


def prepare_ci_environment(namespace):
    """Calls other functions in this module depending on the type of repo under test"""
    repo = os.getenv("REPO")
    # if quay repo name is different from github repo name
    if os.getenv("QUAY_REPO"):
        quay_repo = os.getenv("QUAY_REPO").replace('"', "")
    else:
        quay_repo = repo
    if repo in ("gen3-code-vigil", "gen3-qa"):  # Test repos
        result = modify_env_for_test_repo_pr(namespace)
        assert result.lower() == "success"
    elif repo in ("cdis-manifest", "gitops-qa"):  # Manifest repos
        updated_folders = os.getenv("UPDATED_FOLDERS", "").split(",")
        if len(updated_folders) == 1 and updated_folders[0] == "":
            logger.info("No folders were updated. Skipping tests...")
            # Update SKIP_TESTS to true in GITHUB_ENV
            with open(os.getenv("GITHUB_ENV"), "a") as f:
                f.write("SKIP_TESTS=true\n")
            return
        elif len(updated_folders) > 1:
            # Raise Error if more than 1 folder is updated per PR
            raise Exception(
                "More than 1 folder updated, please update only 1 folder per PR..."
            )
        else:
            updated_folder = updated_folders[0]
            logger.info(f"Setting up env using folder: {updated_folder}")
        result = modify_env_for_manifest_pr(namespace, updated_folder, repo)
        assert result.lower() == "success"
    else:  # Service repos
        quay_tag = (
            os.getenv("BRANCH").replace("(", "_").replace(")", "_").replace("/", "_")
        )
        result = wait_for_quay_build(quay_repo, quay_tag)
        assert result.lower() == "success"
        result = modify_env_for_service_pr(namespace, quay_repo, quay_tag)
        assert result.lower() == "success"
    # generate api keys for test users for the ci env
    result = generate_api_keys_for_test_users(namespace)
    assert result.lower() == "success"
    return result


if __name__ == "__main__":
    result = prepare_ci_environment(os.getenv("NAMESPACE"))
    logger.info(f"Result: {result}")
