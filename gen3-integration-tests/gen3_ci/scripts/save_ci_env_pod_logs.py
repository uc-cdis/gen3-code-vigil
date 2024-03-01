import os

from cdislogging import get_logger
from dotenv import load_dotenv

from utils.jenkins import JenkinsJob

load_dotenv()

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def save_pod_logs(namespace):
    """Save logs from all pods at the end of the test run to help with debugging"""
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
            job.terminate_build(build_num)
            raise Exception("Build timed out. Consider increasing max_duration")
    else:
        raise Exception("Build number not found")


if __name__ == "__main__":
    job_info = save_pod_logs(os.getenv("NAMESPACE"))
    if job_info:
        env_file = os.getenv("GITHUB_ENV")
        with open(env_file, "a") as myfile:
            myfile.write(
                f"POD_LOGS_URL={job_info.get('url', '')}artifact/save-pod-logs/\n"
            )
