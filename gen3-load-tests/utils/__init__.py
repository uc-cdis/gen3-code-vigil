import os
from pathlib import Path

from cdislogging import get_logger

K6_LOAD_TESTING_SCRIPTS_PATH = Path(__file__).parent.parent / "k6_load_testing_scripts"
K6_LOAD_TESTING_OUTPUT_PATH = Path(__file__).parent.parent / "k6_load_testing_output"
SAMPLE_DESCRIPTORS_PATH = Path(__file__).parent.parent / "sample_descriptors"
logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))
