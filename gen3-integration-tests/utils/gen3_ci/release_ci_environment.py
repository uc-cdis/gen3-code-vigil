import os
import requests

from cdislogging import get_logger

from utils.jenkins import JenkinsJob

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def release_ci_environment(namespace):
    job = JenkinsJob(
        "https://jenkins.planx-pla.net",
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "ci-only-unlock-namespace",
    )
    params = {
        "NAMESPACE": namespace,
        "REPO": os.getenv("REPO"),
        "branch": os.getenv("BRANCH"),
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
    namespace = os.getenv("NAMESPACE")
    print(release_ci_environment(namespace))
