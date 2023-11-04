import os
import requests
import sys

from cdislogging import get_logger

from utils.jenkins import JenkinsJob

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def save_pod_logs(namespace):
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "ci-only-save-pod-logs",
    )
    params = {
        "NAMESPACE": namespace,
    }
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num)
        if status == "Completed":
            return job.get_build_info(build_num)
        else:
            logger.error("Build timed out. Consider increasing max_duration")
            return None
    else:
        logger.error("Build number not found")
        return None


if __name__ == "__main__":
    job_info = save_pod_logs(os.getenv("NAMESPACE"))
    logger.info(job_info)
