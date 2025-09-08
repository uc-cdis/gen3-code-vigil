import os
import subprocess

from utils import logger


def setup_env_for_helm(arguments):
    file_path = f"{os.getcwd()}/gen3_ci/scripts/setup_ci_env.sh"
    logger.info(f"File path: {file_path}")
    logger.info(f"Argument: {arguments}")
    result = subprocess.run(
        [file_path] + arguments, capture_output=True, text=True, timeout=1200
    )
    if result.returncode == 0:
        logger.info("Script executed successfully. Output:")
        logger.info(result.stdout)
        return "SUCCESS"
    else:
        logger.info("Script execution failed. Error:")
        logger.info(result.stderr)
        logger.info(result.stdout)
        return "FAILURE"


def prep_dev_env(namespace):
    """
    We can use the CI env's manifest as-is (all services point to master branch)
    Roll the environment
    Run usersync
    """
    helm_branch = "master"
    ci_default_manifest = (
        f"{os.getenv('GITHUB_WORKSPACE')}/gen3-gitops/ci/default/values"
    )
    target_manifest_path = f"{os.getenv('GITHUB_WORKSPACE')}/gen3-gitops/{os.getenv('SOURCE_CONFIG')}/values"

    arguments = [
        namespace,
        "manifest-env-setup",
        helm_branch,
        ci_default_manifest,
        target_manifest_path,
    ]
    return setup_env_for_helm(arguments)


if __name__ == "__main__":
    result = prep_dev_env(os.getenv("NAMESPACE"))
    logger.info(f"Result: {result}")
