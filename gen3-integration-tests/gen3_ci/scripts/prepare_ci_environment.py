import os
import requests
import time

from cdislogging import get_logger
from datetime import datetime

from utils.jenkins import JenkinsJob

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def wait_for_quay_build(repo, tag):
    quay_url_org = "https://quay.io/api/v1/repository/cdis"
    commit_time = datetime.strptime("os.getenv('COMMIT_TIME')", "%Y-%m-%dT%H:%M:%SZ")
    max_tries = 30  # Minutes to wait for image
    found = False
    i = 0
    logger.info(f"Repo - {repo}, image - {tag}")
    while not found and i < max_tries:
        logger.info(f"Waiting for image {repo}:{tag} to be built in quay")
        res = requests.get(f"{quay_url_org}/{repo}/tag")
        if res.status_code == 200:
            branch_images = [x for x in res.json()["tags"] if x["name"] == tag]
            if len(branch_images) >= 1:
                image = branch_images[0]
                image_time = datetime.utcfromtimestamp(image["start_ts"])
                print(image_time)
                if image_time > commit_time:
                    found = True
        i += 1
        time.sleep(60)
    if found:
        return "success"
    if not found:
        logger.error(f"Image with tag {tag} was not found in repo {repo}")
        return "failure"


def modify_env_for_service_pr(namespace, service, tag):
    job = JenkinsJob(
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USERNAME"),
        os.getenv("JENKINS_PASSWORD"),
        "ci-only-modify-env-for-service-pr",
    )
    params = {
        "TARGET_ENVIRONMENT": namespace,
        "SERVICE": service,
        "TAG": tag,
    }
    build_num = job.build_job(params)
    if build_num:
        status = job.wait_for_build_completion(build_num, max_duration=3600)
        if status == "Completed":
            return job.get_build_result(build_num)
        else:
            logger.error("Build timed out. Consider increasing max_duration")
            return "failure"
    else:
        logger.error("Build number not found")
        return "failure"


def prepare_ci_environment(namespace):
    repo = os.getenv("REPO")
    # if quay repo name is different from github repo name
    if os.getenv("QUAY_REPO"):
        quay_repo = os.getenv("QUAY_REPO")
    # quay image tag
    quay_tag = os.getenv("REPO").replace("(", "_").replace(")", "_").replace("/", "_")
    if repo in ("gen3-code-vigl", "gen3-qa"):  # Test repos
        pass
    elif repo in ("cdis-manifest", "gitops-qa"):  # Manifest repos
        pass
    else:  # Service repos
        result = wait_for_quay_build(quay_repo, quay_tag)
        assert result.lower() == "success"
        result = modify_env_for_service_pr(quay_repo, quay_tag, namespace)


if __name__ == "__main__":
    result = prepare_ci_environment(os.getenv("NAMESPACE"))
    logger.info(f"Result: {result}")
