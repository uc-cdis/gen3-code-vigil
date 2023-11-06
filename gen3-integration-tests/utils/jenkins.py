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
        response = requests.get(f"{self.job_url}/api/json", auth=self.auth)
        if response.status_code == 404:
            logger.error("Job not found")
            return None
        return response.json()

    def get_build_info(self, build_number):
        response = requests.get(
            f"{self.job_url}/{build_number}/api/json", auth=self.auth
        )
        if response.status_code == 404:
            logger.error("Build not found")
            return None
        return response.json()

    def is_build_running(self, build_number):
        try:
            running = self.get_build_info(build_number)["building"]
            if running:
                return True
        except Exception:
            return False

    def get_build_result(self, build_number):
        info = self.get_build_info(build_number)
        return info["result"]

    def get_console_output(self, build_number):
        response = requests.get(
            f"{self.job_url}/{build_number}/consoleText", auth=self.auth
        )
        return response.text

    def build_job(self, parameters=None):
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

    def wait_for_build_completion(self, build_number, max_duration=300):
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


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "ci-only-fetch-portal-config",
    )
    params = {
        "TARGET_ENVIRONMENT": "qa-heal",
        "COMMAND": "gen3 secrets decode portal-config gitops.json | jq '.discoveryConfig.minimalFieldMapping.uid'",
    }
    # print(job.get_job_info())
    # build_num = job.build_job(params)
    # if build_num:
    #     status = job.wait_for_build_completion(build_num)
    #     if status == 'Completed':
    #         print(job.get_build_result(build_num))

    print(job.get_artifact_content(3, "gitops.txt"))
