import json
import os
import pytest

from cdislogging import get_logger

from utils import test_setup as setup
from utils import TEST_DATA_PATH_OBJECT

# Using dotenv to simplify setting up env vars locally
from dotenv import load_dotenv

load_dotenv()

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def pytest_configure(config):
    # Compute hostname and namespace
    hostname = os.getenv("HOSTNAME")
    namespace = os.getenv("NAMESPACE")
    tested_env = os.getenv("TESTED_ENV")
    assert hostname or namespace, "Hostname and namespace undefined"
    if hostname and not namespace:
        namespace = hostname.split(".")[0]
    if namespace and not hostname:
        hostname = f"{namespace}.planx-pla.net"
    pytest.hostname = hostname
    pytest.namespace = namespace
    # TODO: tested_env will differ from namespace for manifest PRs
    pytest.tested_env = tested_env or namespace

    # Compute root_url
    pytest.root_url = f"https://{hostname}"

    # Accounts used for testing
    pytest.users = {}
    pytest.users["main_account"] = "cdis.autotest@gmail.com"  # default user
    pytest.users["indexing_account"] = "ctds.indexing.test@gmail.com"  # indexing admin

    # Generate api key and auth headers
    pytest.api_keys = {}
    pytest.auth_headers = {}
    for user in pytest.users:
        (
            pytest.api_keys[user],
            pytest.auth_headers[user],
        ) = setup.get_api_key_and_auth_header(user)

    if not hasattr(config, "workerinput"):
        # Get configuration files
        setup.get_configuration_files()
        # Generate test data
        setup.generate_graph_data()

    # Compute root url for portal
    try:
        manifest = json.loads(
            (TEST_DATA_PATH_OBJECT / "configuration/manifest.json").read_text()
        )
    except FileNotFoundError:
        logger.error(
            "manifest.json not found. It should have been fetched by `get_configuration_files`..."
        )
        raise
    if manifest.get("data", {}).get("frontend_root", "") == "gen3ff":
        pytest.root_url_portal = f"https://{pytest.hostname}/portal"
    else:
        pytest.root_url_portal = pytest.root_url
