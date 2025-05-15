import os
from pathlib import Path

from cdislogging import get_logger

GEN_LOAD_TESTING_PATH = Path(__file__).parent.parent
LOAD_TESTING_SCRIPTS_PATH = Path(__file__).parent.parent / "load_testing_scripts"
LOAD_TESTING_OUTPUT_PATH = Path(__file__).parent.parent / "output"
TEST_DATA_PATH_OBJECT = Path(__file__).parent.parent / "test_data"
logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))
