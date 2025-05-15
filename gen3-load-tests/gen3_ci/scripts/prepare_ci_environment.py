import json
import os
from pathlib import Path

from dotenv import load_dotenv
from utils import logger, test_setup
from utils.jenkins import JenkinsJob

load_dotenv()


def modify_env_for_test_repo_pr(namespace):
    """
    We can use the test env's manifest as-is (all services point to master branch)
    Roll the environment
    Run usersync
    """
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "ci-only-modify-env-for-test-repo-pr",
    )
    params = {
        "NAMESPACE": namespace,
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


def generate_api_keys_for_test_users(namespace):
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
    }
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num)
        if status == "Completed":
            res = job.get_build_result(build_num)
            if res.lower() == "success":
                for user in test_users:
                    api_key = json.loads(
                        job.get_artifact_content(build_num, f"{namespace}_{user}.json")
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


def prepare_ci_environment(namespace):
    """Calls other functions in this module depending on the type of repo under test"""
    repo = os.getenv("REPO")
    # if quay repo name is different from github repo name
    if repo in ("gen3-code-vigil", "gen3-qa"):  # Test repos
        result = modify_env_for_test_repo_pr(namespace)
        assert result.lower() == "success"
    else:
        raise Exception("Load tests are run from test repository only.")
    # generate api keys for test users for the ci env
    result = generate_api_keys_for_test_users(namespace)
    assert result.lower() == "success"
    return result


if __name__ == "__main__":
    result = prepare_ci_environment(os.getenv("NAMESPACE"))
    logger.info(f"Result: {result}")
