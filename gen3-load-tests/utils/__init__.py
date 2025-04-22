import os
from pathlib import Path

from cdislogging import get_logger

LOAD_TESTING_SCRIPTS_PATH = Path(__file__).parent.parent / "load_testing_scripts"
LOAD_TESTING_OUTPUT_PATH = Path(__file__).parent.parent / "output"
SAMPLE_DESCRIPTORS_PATH = Path(__file__).parent.parent / "sample_descriptors"
TEST_DATA_PATH_OBJECT = Path(__file__).parent.parent / "test_data"
logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))
