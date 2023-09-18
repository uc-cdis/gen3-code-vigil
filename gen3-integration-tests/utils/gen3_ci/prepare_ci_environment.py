import os
import requests
import sys

from cdislogging import get_logger

from utils.jenkins import JenkinsJob

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def wait_for_image_build(repo, branch):
    branch = branch.replace("(", "_").replace(")", "_").replace("/", "_")
    if os.getenv("QUAY_REPO"):
        repo = os.getenv("QUAY_REPO")


def prepare_ci_environment(namespace):
    repo = os.getenv("REPO")

    if repo in ("gen3-code-vigl", "gen3-qa"):  # Test repos
        pass
    elif repo in ("cdis-manifest", "gitops-qa"):  # Manifest repos
        pass
    else:  # Service repos
        pass

    # Roll all pods
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "ci-only-run-gen3-command",
    )
    params = {
        "TARGET_ENVIRONMENT": namespace,
        "COMMAND": "gen3 reset",
    }
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num, max_duration=1800)
        if status == "Completed":
            return job.get_build_result(build_num)
        else:
            logger.error("Build timed out. Consider increasing max_duration")
            return None
    else:
        logger.error("Build number not found")
        return None

    # Run usersync
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "ci-only-run-gen3-job",
    )
    params = {
        "TARGET_ENVIRONMENT": namespace,
        "JOB_NAME": "usersync",
    }
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num)
        if status == "Completed":
            return job.get_build_result(build_num)
        else:
            logger.error("Build timed out. Consider increasing max_duration")
            return None
    else:
        logger.error("Build number not found")
        return None


if __name__ == "__main__":
    result = prepare_ci_environment(os.getenv("NAMESPACE"))
    logger.info(f"Result: {result}")
