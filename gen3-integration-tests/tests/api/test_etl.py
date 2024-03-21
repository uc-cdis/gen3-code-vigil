import pytest
import os

import utils.gen3_admin_tasks as gat

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.tube
class TestETL:
    def test_etl(self):
        logger.info("Running etl for the first time")
        gat.run_gen3_job(pytest.namespace, "etl")

        logger.info("Running etl for the second time")
        gat.run_gen3_job(pytest.namespace, "etl")
