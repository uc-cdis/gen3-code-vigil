import os
import requests
import time
import traceback
from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))

# Jobs listed on https://jenkins.planx-pla.net/view/CI%20Jobs/


class JenkinsJob(object):
    def __init__(self, jenkins_url, username, password, job_name):
        self.job_url = f"{jenkins_url}/job/{job_name}"
        self.auth = (username, password)
        self.job_name = job_name

    def get_job_info(self):
        """
        Get jenkins job details (not a single run).
        Job is the job configured in jenkins.
        """
        response = requests.get(f"{self.job_url}/api/json", auth=self.auth)
        if response.status_code == 404:
            logger.error("Job not found")
            return None
        return response.json()

    def get_build_info(self, build_number):
        """
        Get build details.
        A build is a single run of the job configured in jenkins.
        """
        response = requests.get(
            f"{self.job_url}/{build_number}/api/json", auth=self.auth
        )
        if response.status_code == 404:
            logger.error("Build not found")
            return None
        return response.json()

    def is_build_running(self, build_number):
        """Check if there is an active run for the job"""
        try:
            running = self.get_build_info(build_number)["building"]
            if running:
                return True
        except Exception:
            return False

    def get_build_result(self, build_number):
        """Get result of a run"""
        info = self.get_build_info(build_number)
        return info["result"]

    def get_console_output(self, build_number):
        """Get the console logs of a run"""
        response = requests.get(
            f"{self.job_url}/{build_number}/consoleText", auth=self.auth
        )
        return response.text

    def build_job(self, parameters=None):
        """
        Trigger a run / build of the job.
        Returns the build number if triggered successfully.
        """
        logger.info(f"Triggering build for job {self.job_url}")
        url = f"{self.job_url}/build"
        if parameters:
            url += "WithParameters?%s" % "&".join(
                f"{k}={v}" for k, v in parameters.items()
            )
        response = requests.post(url, auth=self.auth)
        max_retries = 6
        current_retry = 0
        while response.status_code == 404 and current_retry < max_retries:
            current_retry += 1
            logger.info(f"Retrying - attempt {current_retry}")
            time.sleep(10)
            response = requests.post(url, auth=self.auth)
        queue_item_url = response.headers["Location"]
        if response.status_code == 201:
            build_started = False
            while build_started is False:
                logger.info("Waiting for build to start ...")
                time.sleep(10)
                res = requests.get(queue_item_url + "api/json", auth=self.auth).json()
                if "executable" in res:
                    build_started = True
            build_number = res["executable"]["number"]
            logger.info(f"Build number {build_number} triggered successfully")
            return build_number
        else:
            logger.error("Failed to start build")
            return None

    def wait_for_build_completion(self, build_number, max_duration=600):
        """
        Wait for a run to complete.
        Default maximum wait time is 10 minutes, and can be configured.
        If the run is not complete within the max set, this function errors out.
        """
        start = time.time()
        status = None

        while True:
            elapsed = time.time() - start
            if not self.is_build_running(build_number):
                logger.info("Job completed")
                status = "Completed"
                break
            if elapsed > max_duration:
                logger.error("Max duration reached, stopping monitor")
                status = "Timed Out"
                break
            else:
                logger.info("Waiting for job completion ...")
                time.sleep(60)
        return status

    def get_artifact_content(self, build_number, artifact_name):
        """Get the contents of an artifact archived for the specific run"""
        try:
            artifacts = requests.get(
                f"{self.job_url}/{build_number}/api/json", auth=self.auth
            ).json()["artifacts"]
            artifact_rel_path = [
                d for d in artifacts if d["fileName"] == artifact_name
            ][0]["relativePath"]
            response = requests.get(
                f"{self.job_url}/{build_number}/artifact/{artifact_rel_path}",
                auth=self.auth,
            )
            return response.text
        except Exception as e:
            logger.error(e)
            logger.error(traceback.format_exc())

    def terminate_build(self, build_num):
        """
        Terminate a build / run of the job.
        """
        logger.info(f"Terminating build {build_num} for job {self.job_url}")
        try:
            response = requests.post(f"{self.job_url}/{build_num}/stop", auth=self.auth)
            if response.status_code == 200:
                return "SUCCESS"
            else:
                response = requests.post(
                    f"{self.job_url}/{build_num}/term", auth=self.auth
                )
                if response.status_code == 200:
                    return "SUCCESS"
                else:
                    response = requests.post(
                        f"{self.job_url}/{build_num}/kill", auth=self.auth
                    )
                    if response.status_code == 200:
                        return "SUCCESS"
                    else:
                        logger.error(
                            f"Failed to terminate build {build_num}. Stop manually at {self.job_url}/{build_num}"
                        )
                        return "FAILURE"
        except Exception:
            logger.error(
                f"Failed to terminate build {build_num}. Stop manually at {self.job_url}/{build_num}"
            )
            return "FAILURE"


if __name__ == "__main__":
    # The code below is to help with debugging changes to the above
    import os
    from dotenv import load_dotenv

    load_dotenv()

    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "ci-only-modify-env-for-test-repo-pr",
    )
    params = {
        "TARGET_ENVIRONMENT": "jenkins-blood",
    }
    print(job.get_job_info())
    build_num = job.build_job(params)
    print(job.terminate_build(build_num))
