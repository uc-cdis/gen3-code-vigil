import os

import pytest
import requests
from cdislogging import get_logger
from gen3.auth import Gen3Auth
from gen3.jobs import Gen3Jobs
from gen3.query import Gen3Query

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.gen3sdk
class TestGen3Sdk:
    @pytest.mark.skipif(
        "batch-export" not in pytest.enabled_sower_jobs,
        reason="batch-export is not part of sower in manifest",
    )
    def test_gen3_jobs_list_jobs(self):
        """
        Scenario: Gen3Jobs List jobs
        Steps:
            1.
        """
        BATCH_EXPORT_JOB = "batch-export"
        JOB_INPUT = {
            "action": "batch-export",
        }
        auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )
        gen3jobs = Gen3Jobs(endpoint=pytest.root_url, auth_provider=auth)
        create_job = gen3jobs.create_job(job_name=BATCH_EXPORT_JOB, job_input=JOB_INPUT)
        status = "Running"
        while status == "Running":
            status = gen3jobs.get_status(create_job.get("uid")).get("status")

        get_output = gen3jobs.get_output(create_job.get("uid"))
        get_status = gen3jobs.get_status(create_job.get("uid"))
        list_jobs = gen3jobs.list_jobs()
        assert (
            "No studies or files provided" in get_output["output"]
        ), f"Expected 'No studies or files provided' but got {get_output}"
        assert (
            "Completed" in get_status["status"]
        ), f"Expected status completed but got {get_status}"
        logger.info(f"List of all jobs running: {list_jobs}")
