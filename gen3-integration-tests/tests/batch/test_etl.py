import pytest
import os

import utils.gen3_admin_tasks as gat

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.tube
class TestETL:
    @classmethod
    def setup_class(cls):
        gat.clean_up_indices(pytest.namespace)

    @classmethod
    def teardown_class(cls):
        gat.clean_up_indices(pytest.namespace)

    def test_etl(self):
        """
        Scenario: Test ETL
        Steps:
            1. Clean up indices before the test run
            2. Run the ETL job for the first time
            3. Run the ETL job for the second time
            4. Check if the index version has increased
            5. Clean up indices after the test run
        """
        logger.info("Running etl for the first time")
        gat.run_gen3_job(pytest.namespace, "etl")

        logger.info("Running etl for the second time")
        gat.run_gen3_job(pytest.namespace, "etl")

        gat.check_indices_after_etl(pytest.namespace)
