import os

import pytest
import utils.gen3_admin_tasks as gat
from gen3.auth import Gen3Auth
from services.graph import GraphDataTools
from utils import logger


@pytest.mark.skipif(
    "sheepdog" not in pytest.deployed_services,
    reason="sheepdog service is not running on this environment",
)
@pytest.mark.tube
class TestETL:
    @classmethod
    def setup_class(cls):
        gat.clean_up_indices(test_env_namespace=pytest.namespace)
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        logger.info("Submitting test records")
        sd_tools.submit_all_test_records()

    @classmethod
    def teardown_class(cls):
        gat.clean_up_indices(test_env_namespace=pytest.namespace)

    def test_etl(self):
        """
        Scenario: Test ETL
        Steps:
            1. Clean-up indices before the test run
            2. Run the ETL job for the first time
            3. Run the ETL job for the second time
            4. Check if the index version has increased
            5. Clean-up indices after the test run
        """
        logger.info("Running etl for the first time")
        gat.run_gen3_job("etl", test_env_namespace=pytest.namespace)

        logger.info("Running etl for the second time")
        gat.run_gen3_job("etl", test_env_namespace=pytest.namespace)

        gat.check_indices_after_etl(test_env_namespace=pytest.namespace)
