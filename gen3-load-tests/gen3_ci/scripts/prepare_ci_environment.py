import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from utils import HELM_SCRIPTS_PATH_OBJECT, TEST_DATA_PATH_OBJECT, logger, test_setup

load_dotenv()


def setup_env_for_helm(arguments):
    file_path = HELM_SCRIPTS_PATH_OBJECT / "setup_ci_env.sh"
    logger.info(f"File path: {file_path}")
    logger.info(f"Argument: {arguments}")
    result = subprocess.run(
        [file_path] + arguments, capture_output=True, text=True, timeout=1200
    )
    if result.returncode == 0:
        logger.info("Script executed successfully. Logs:")
        logger.info(result.stdout)
        return "SUCCESS"
    else:
        logger.info("Script execution failed. Logs:")
        logger.info(result.stderr)
        logger.info(result.stdout)
        return "failure"


def modify_env_for_test_repo_pr(namespace):
    """
    We can use the test env's manifest as-is (all services point to master branch)
    Roll the environment
    Run usersync
    """
    perf_default_manifest = (
        f"{os.getenv('GITHUB_WORKSPACE')}/gen3-gitops-ci/ci/default/values"
    )
    arguments = [
        os.getenv("NAMESPACE"),
        "master",
        perf_default_manifest,
    ]
    return setup_env_for_helm(arguments)


def generate_api_keys_for_test_users(namespace):
    cmd = [
        (HELM_SCRIPTS_PATH_OBJECT / "generate_api_keys.sh"),
        (TEST_DATA_PATH_OBJECT / "test_setup" / "users.csv"),
        os.getenv("HOSTNAME"),
        os.getenv("NAMESPACE"),
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        logger.info(result.stdout.strip().replace("'", ""))
        return "SUCCESS"
    else:
        logger.info(result.stdout)
        raise Exception(f"Got error: {result.stderr}")


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
