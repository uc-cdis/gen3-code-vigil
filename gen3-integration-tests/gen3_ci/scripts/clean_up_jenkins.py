import os

from cdislogging import get_logger

from utils.jenkins import JenkinsJob

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def clean_up_jenkins():
    """Stop pending job for prepping the test environment"""
    #
    # Stop running job to select CI env
    #
    job_name, build_num = os.getenv("SELECT_CI_ENV_JOB_INFO").split("|")
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        job_name,
    )
    if job.is_build_running(build_num):
        logger.info("CI environment is being selected ...")
        job.terminate_build(build_num)
    #
    # Stop running job to prepare CI env
    #
    job_name, build_num = os.getenv("PREPARE_CI_ENV_JOB_INFO").split("|")
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        job_name,
    )
    if job.is_build_running(build_num):
        logger.info("CI environment is being prepped ...")
        job.terminate_build(build_num)


if __name__ == "__main__":
    clean_up_jenkins()
