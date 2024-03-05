import os
import pytest

from utils import test_setup as setup

from utils.misc import one_worker_only

# Using dotenv to simplify setting up env vars locally
from dotenv import load_dotenv

load_dotenv()


def pytest_configure(config):
    # Compute hostname and namespace
    hostname = os.getenv("HOSTNAME")
    namespace = os.getenv("NAMESPACE")
    assert hostname or namespace, "Hostname and namespace undefined"
    if hostname and not namespace:
        namespace = hostname.split(".")[0]
    if namespace and not hostname:
        hostname = f"{namespace}.planx-pla.net"
    pytest.namespace = namespace
    # TODO: tested_env will differ from namespace for manifest PRs
    pytest.tested_env = namespace

    # Compute root_url
    pytest.root_url = f"https://{hostname}"

    # Accounts used for testing
    pytest.users = {}
    pytest.users["main_account"] = "cdis.autotest@gmail.com"  # default user
    pytest.users["indexing_account"] = "ctds.indexing.test@gmail.com"  # indexing admin
    pytest.users[
        "dcf_integration_user"
    ] = "dcf-integration-test-0@planx-pla.net"  # user0 dcf_integration_test

    # Generate api key and auth headers
    pytest.api_keys = {}
    pytest.auth_headers = {}
    for user in pytest.users:
        (
            pytest.api_keys[user],
            pytest.auth_headers[user],
        ) = setup.get_api_key_and_auth_header(user)


@pytest.fixture(autouse=True, scope="session")
@one_worker_only(wait_secs=5, max_wait_minutes=15)
def setup_tests():
    # Get configuration files
    setup.get_configuration_files()
    # Generate test data
    setup.generate_graph_data()