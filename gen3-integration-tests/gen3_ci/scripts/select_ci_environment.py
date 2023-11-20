import os
import requests
import sys

from cdislogging import get_logger

from utils.jenkins import JenkinsJob

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def select_ci_environment(namespaces):
    """
    Select available test environment.
    Lock it to prevent being used by other PRs.
    """
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "ci-only-select-and-lock-namespace",
    )
    params = {
        "AVAILABLE_NAMESPACES": namespaces,
        "REPO": os.getenv("REPO"),
        "BRANCH": os.getenv("BRANCH"),
    }
    build_num = job.build_job(params)
    if build_num:
        env_file = os.getenv("GITHUB_ENV")
        with open(env_file, "a") as myfile:
            myfile.write(f"SELECT_CI_ENV_JOB_INFO={job.job_name}|{build_num}")
        status = job.wait_for_build_completion(build_num, max_duration=1800)
        if status == "Completed":
            return job.get_artifact_content(build_num, "namespace.txt")
        else:
            logger.error("Build timed out. Consider increasing max_duration")
            job.terminate_build(build_num)
            return None
    else:
        logger.error("Build number not found")
        return None


if __name__ == "__main__":
    if len(sys.argv) > 1:
        namespace = sys.argv[1]
        logger.info(f"Namespace {namespace} was set as a PR label")
        namespaces = namespace
    else:
        if os.getenv("REPO") in ["cdis-manifest", "gitops-qa"]:
            env_pool = "releases"
        else:
            env_pool = "services"
        logger.info("Namespace was not set as a PR labels")
        res = requests.get(
            f"https://cdistest-public-test-bucket.s3.amazonaws.com/jenkins-envs-{env_pool}.txt"
        )
        namespaces = ",".join(res.text.strip().split("\n"))

    selected_ns = select_ci_environment(namespaces)
    logger.info(f"Selected namespace: {selected_ns}")

    env_file = os.getenv("GITHUB_ENV")
    with open(env_file, "a") as myfile:
        myfile.write(f"NAMESPACE={selected_ns}")
