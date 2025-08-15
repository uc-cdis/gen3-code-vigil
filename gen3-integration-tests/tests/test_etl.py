import os

import pytest
import utils.gen3_admin_tasks as gat
from gen3.auth import Gen3Auth
from services.graph import GraphDataTools
from utils import logger


@pytest.mark.skipif(
    os.getenv("ETL_ENABLED") == "false",
    reason="ETL is not enabled on this environment",
)
@pytest.mark.skipif(
    gat.validate_button_in_portal_config(
        gat.get_portal_config(), search_button="export-to-pfb"
    ),
    reason="ETL Validation is performed in the PFB Export test",
)
@pytest.mark.tube
@pytest.mark.etl
class TestETL:
    @classmethod
    def setup_class(cls):
        cls.auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        cls.sd_tools = GraphDataTools(
            auth=cls.auth, program_name="jnkns", project_code="jenkins2"
        )
        logger.info("Submitting test records")
        cls.sd_tools.submit_all_test_records()

    @classmethod
    def teardown_class(cls):
        cls.sd_tools.delete_all_records()

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
        before_indices_versions = gat.check_indices_etl_version(
            test_env_namespace=pytest.namespace
        )
        logger.info("Running etl")
        gat.run_gen3_job("etl", test_env_namespace=pytest.namespace)

        after_indices_versions = gat.check_indices_etl_version(
            test_env_namespace=pytest.namespace
        )

        logger.info(f"Indices before ETL: {before_indices_versions}")
        logger.info(f"Indices after ETL: {after_indices_versions}")

        for index in after_indices_versions.keys():
            version_diff = (
                after_indices_versions[index] - before_indices_versions[index]
            )
            assert (
                version_diff == 1
            ), f"Version expected to increase by 1, but increased by {version_diff} for index {index}"
