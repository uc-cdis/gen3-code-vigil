import os

import pytest
from cdislogging import get_logger
from gen3.auth import Gen3Auth
from gen3.jobs import Gen3Jobs
from gen3.query import Gen3Query

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.gen3sdk
class TestGen3Sdk:
    def test_gen3_jobs_list_jobs(self):
        """
        Scenario: Gen3Jobs List jobs
        Steps:
            1.
        """
        PFB_EXPORT_JOB = "export"
        JOB_INPUT = {
            "action": "export",
            "input": {"filter": {"IN": {"project_id": ["Canine-NHGRI"]}}},
        }
        auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )
        gen3jobs = Gen3Jobs(endpoint=pytest.root_url, auth_provider=auth)
        create_job = gen3jobs.async_run_job_and_wait(
            job_name=PFB_EXPORT_JOB, job_input=JOB_INPUT
        )
        logger.info(create_job)
        status = "Running"
        while status == "Running":
            status = gen3jobs.get_status(create_job.get("uid")).get("status")

        get_output = gen3jobs.get_output(create_job.get("uid"))
        logger.info(get_output)
        list_jobs = gen3jobs.list_jobs()
        logger.info(list_jobs)
