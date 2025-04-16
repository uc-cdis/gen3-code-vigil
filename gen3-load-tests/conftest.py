import os
import shutil

import pytest

# Using dotenv to simplify setting up env vars locally
from dotenv import load_dotenv
from utils import K6_LOAD_TESTING_OUTPUT_PATH
from utils import test_setup as setup

load_dotenv()
collect_ignore = ["test_setup.py"]


def pytest_configure(config):
    # Compute hostname and namespace
    pytest.hostname = os.getenv("HOSTNAME")
    # Compute root_url
    pytest.root_url = f"https://{pytest.hostname}"

    # Generate api key and auth headers
    pytest.users = {
        "main_account": "main@example.org",
        "indexing_account": "indexing@example.org",
    }

    # Minimum pass percentage for each load test
    pytest.pass_threshold = 99
    pytest.api_keys = {}
    for user in pytest.users:
        pytest.api_keys[user] = setup.get_api_key(user)

    K6_LOAD_TESTING_OUTPUT_PATH.mkdir(parents=True, exist_ok=True)


# def pytest_unconfigure(config):
#     if os.path.exists(K6_LOAD_TESTING_OUTPUT_PATH):
#         shutil.rmtree(K6_LOAD_TESTING_OUTPUT_PATH)
