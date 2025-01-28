import os

from utils import logger
from utils.jenkins import JenkinsJob


def release_ci_environment(namespace, cloud_auto_branch):
    """Remove the lock from the test environment and make it available for other PRs"""
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
        "CLOUD_AUTO_BRANCH": cloud_auto_branch,
    }
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num)
        if status == "Completed":
            return job.get_build_result(build_num)
        else:
            job.terminate_build(build_num)
            raise Exception("Build timed out. Consider increasing max_duration")
    else:
        raise Exception("Build number not found")


if __name__ == "__main__":
    namespace = os.getenv("NAMESPACE")
    cloud_auto_branch = os.getenv("CLOUD_AUTO_BRANCH")
    result = release_ci_environment(namespace, cloud_auto_branch)
    logger.info(f"RESULT: {result}")
