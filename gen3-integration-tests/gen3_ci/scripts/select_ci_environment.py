import os
import requests
import sys

from utils import logger

from utils.jenkins import JenkinsJob


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
            myfile.write(f"SELECT_CI_ENV_JOB_INFO={job.job_name}|{build_num}\n")
        status = job.wait_for_build_completion(build_num, max_duration=1800)
        if status == "Completed":
            return job.get_artifact_content(build_num, "namespace.txt")
        else:
            job.terminate_build(build_num)
            raise Exception("Build timed out. Consider increasing max_duration")
    else:
        raise Exception("Build number not found")


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
        logger.info("Namespace was not set as a PR label")
        res = requests.get(
            f"https://cdistest-public-test-bucket.s3.amazonaws.com/jenkins-envs-{env_pool}.txt"
        )
        namespaces = ",".join(res.text.strip().split("\n"))

    try:
        selected_ns = select_ci_environment(namespaces)
    except Exception:
        logger.error("Unable to select namespace!")
        raise
    logger.info(f"Selected namespace: {selected_ns}")

    env_file = os.getenv("GITHUB_ENV")
    with open(env_file, "a") as myfile:
        myfile.write(f"NAMESPACE={selected_ns}\n")
