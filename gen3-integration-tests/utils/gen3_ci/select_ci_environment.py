import os
import requests

from cdislogging import get_logger

from utils.jenkins import JenkinsJob

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def select_ci_environment(namespaces):
    job = JenkinsJob(
        "https://jenkins.planx-pla.net",
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "ci-only-select-and-lock-namespace",
    )
    params = {
        "AVAILABLE_NAMESPACES": namespaces,
        "REPO": os.getenv("REPO"),
        "branch": os.getenv("BRANCH"),
    }
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num)
        if status == "Completed":
            return job.get_artifact_content(build_num, "namespace.txt")
        else:
            logger.error("Build timed out. Consider increasing max_duration")
            return None
    else:
        logger.error("Build number not found")
        return None


if __name__ == "__main__":
    res = requests.get(
        "https://cdistest-public-test-bucket.s3.amazonaws.com/jenkins-envs.txt"
    )
    namespaces = ",".join(res.text.strip().split("\n"))
    print(select_ci_environment(namespaces))
