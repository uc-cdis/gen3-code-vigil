import os
import time

import requests
from utils import logger
from utils.misc import retry

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
            raise Exception("Job not found")
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
            raise Exception("Build not found")
        return response.json()

    def is_build_running(self, build_number):
        """Check if there is an active run for the job"""
        try:
            running = self.get_build_info(build_number)["building"]
            if running:
                return True
        except Exception:
            return False

    @retry(times=4, delay=15, exceptions=(AssertionError,))
    def get_build_result(self, build_number):
        """Get result of a run"""
        info = self.get_build_info(build_number)
        assert "result" in info
        assert info["result"] is not None
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
        while response.status_code != 201 and current_retry < max_retries:
            current_retry += 1
            logger.info(f"Retrying - attempt {current_retry}")
            time.sleep(10)
            response = requests.post(url, auth=self.auth)
        if current_retry == max_retries:
            raise Exception(
                f"Failed to start jenkins job at '{url}': {response.status_code}"
            )

        if response.status_code == 201:
            queue_item_url = response.headers["Location"]
            build_started = False
            while build_started is False:
                logger.info("Waiting for build to start...")
                time.sleep(10)
                res = requests.get(queue_item_url + "api/json", auth=self.auth).json()
                if "executable" in res:
                    build_started = True
            build_number = res["executable"]["number"]
            logger.info(f"Build number {build_number} triggered successfully")
            return build_number
        else:
            raise Exception(f"Failed to get jenkins job output: {response.status_code}")

    def wait_for_build_completion(self, build_number, max_duration=1200):
        """
        Wait for a run to complete.
        Default maximum wait time is 20 minutes, and can be configured.
        If the run is not complete within the max set, this function errors out.
        """
        start = time.time()
        status = None

        logger.info(f"Waiting for job completion for up to {max_duration}s")
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
                # TODO log the link to the blue ocean console instead
                logger.info(
                    f"({elapsed}s) Waiting for completion of job {self.job_url}/{build_number}..."
                )
                time.sleep(60)
        return status

    @retry(times=2, delay=10, exceptions=(AssertionError,))
    def get_artifact_content(self, build_number, artifact_name):
        """Get the contents of an artifact archived for the specific run"""
        url = f"{self.job_url}/{build_number}/api/json"
        response = requests.get(url, auth=self.auth)
        assert response.status_code == 200, f"Unable to get artifacts at '{url}'"

        artifacts = response.json()["artifacts"]
        matching_artifacts = [d for d in artifacts if d["fileName"] == artifact_name]
        assert (
            len(matching_artifacts) > 0
        ), f"No artifacts found with name '{artifact_name}'"
        artifact_rel_path = matching_artifacts[0]["relativePath"]

        url = f"{self.job_url}/{build_number}/artifact/{artifact_rel_path}"
        response = requests.get(
            url,
            auth=self.auth,
        )
        assert response.status_code == 200, f"Unable to get artifacts at '{url}'"
        return response.text

    def terminate_build(self, build_num):
        """
        Terminate a build / run of the job.
        """
        logger.info(f"Terminating build for job {self.job_url}/{build_num}")
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
    from dotenv import load_dotenv

    load_dotenv()

    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "ci-only-modify-env-for-test-repo-pr",
    )
    params = {
        "NAMESPACE": "jenkins-blood",
    }
    print(job.get_job_info())
    build_num = job.build_job(params)
    if not build_num:
        logger.error("Build number not found")
        exit(1)
    print(job.terminate_build(build_num))
