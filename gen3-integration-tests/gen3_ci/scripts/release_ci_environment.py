import os

from cdislogging import get_logger

from utils.jenkins import JenkinsJob

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def release_ci_environment(namespace):
    """
    Stop pending job for prepping the test environment.
    Remove the lock from the test environment and make it available for other PRs.
    """
    #
    # Stop running job to prep CI env
    #
    job_name, build_num = os.getenv("PREP_CI_ENV_JOB_INFO").split("|")
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        job_name,
    )
    if job.is_build_running(build_num):
        logger.info("CI environment is being prepped ...")
        res = job.terminate_build(build_num)
    # Unlock namespace
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "ci-only-unlock-namespace",
    )
    params = {
        "NAMESPACE": namespace,
        "REPO": os.getenv("REPO"),
        "BRANCH": os.getenv("BRANCH"),
    }
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num)
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


if __name__ == "__main__":
    namespace = os.getenv("NAMESPACE")
    result = release_ci_environment(namespace)
    logger.info(f"RESULT: {result}")
