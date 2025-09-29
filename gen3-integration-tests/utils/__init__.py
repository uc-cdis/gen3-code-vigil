import os
from pathlib import Path

from cdislogging import get_logger

TEST_DATA_PATH_OBJECT = Path(__file__).parent.parent / "test_data"
HELM_SCRIPTS_PATH_OBJECT = Path(__file__).parent.parent / "gen3_ci" / "scripts"

worker_id = os.getenv("PYTEST_XDIST_WORKER", "master")
log_filename = f"output/logs_{worker_id}.log"  # one log file per worker
logger = get_logger(
    __name__, file_name=log_filename, log_level=os.getenv("LOG_LEVEL", "info")
)
