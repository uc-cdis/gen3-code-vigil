import os
from pathlib import Path

from cdislogging import get_logger

TEST_DATA_PATH_OBJECT = Path(__file__).parent.parent / "test_data"
HELM_SCRIPTS_PATH_OBJECT = Path(__file__).parent.parent / "gen3_ci" / "scripts"
logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))
