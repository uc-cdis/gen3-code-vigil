import json
import os
import pytest
import shutil

from xdist import is_xdist_controller
from xdist.scheduler import LoadScopeScheduling

from utils import logger
from utils import test_setup as setup
from utils import TEST_DATA_PATH_OBJECT

# Using dotenv to simplify setting up env vars locally
from dotenv import load_dotenv

load_dotenv()
requires_fence_client_marker_present = False


class XDistCustomPlugin:
    def __init__(self):
        self._nodes = None

    @pytest.hookimpl(tryfirst=True)
    def pytest_collection(self, session):
        if is_xdist_controller(session):
            self._nodes = {item.nodeid: item for item in session.perform_collect(None)}
            return True

    def pytest_xdist_make_scheduler(self, config, log):
        return CustomScheduling(config, log, nodes=self._nodes)


class CustomScheduling(LoadScopeScheduling):
    def __init__(self, config, log, *, nodes):
        super().__init__(config, log)
        self._nodes = nodes

    def _split_scope(self, nodeid):
        node = self._nodes[nodeid]
        # Run all tests with marker workspace to run serially (same worker)
        if node.get_closest_marker("workspace"):
            return "__workspace__"

        if node.get_closest_marker("requires_fence_client"):
            return "__requires_fence_client__"

        # otherwise, each test is in its own scope
        return nodeid.rsplit("::", 1)[0]


def pytest_collection_finish(session):
    global requires_fence_client_marker_present
    # Iterate through the collected test items
    if not hasattr(session.config, "workerinput"):
        for item in session.items:
            # Access the markers for each test item
            markers = item.keywords
            for marker_name, marker in markers.items():
                if marker_name == "requires_fence_client":
                    setup.get_fence_client_info()
                    requires_fence_client_marker_present = True
                    return


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

    # Clients used for testing
    pytest.clients = {}
    # Accounts used for testing
    pytest.users = {}
    pytest.users["main_account"] = "cdis.autotest@gmail.com"  # default user
    pytest.users["indexing_account"] = "ctds.indexing.test@gmail.com"  # indexing admin
    pytest.users["auxAcct1_account"] = "dummy-one@planx-pla.net"  # auxAcct1 user
    pytest.users["auxAcct2_account"] = "smarty-two@planx-pla.net"  # auxAcct2 user
    pytest.users["user0_account"] = (
        "dcf-integration-test-0@planx-pla.net"  # user0 dcf_integration_test
    )
    pytest.users["user1_account"] = (
        "dcf-integration-test-1@planx-pla.net"  # user1 dcf_integration_test
    )
    pytest.users["user2_account"] = (
        "dcf-integration-test-2@planx-pla.net"  # user2 dcf_integration_test
    )

    # Generate api key and auth headers
    pytest.api_keys = {}
    pytest.auth_headers = {}
    for user in pytest.users:
        (
            pytest.api_keys[user],
            pytest.auth_headers[user],
        ) = setup.get_api_key_and_auth_header(user)

    # Prevent pytest-xdist from running this on each worker individually
    if not hasattr(config, "workerinput"):
        # Get configuration files
        setup.get_configuration_files()

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
    if manifest.get("global", {}).get("frontend_root", "") == "gen3ff":
        pytest.root_url_portal = f"https://{pytest.hostname}/portal"
    else:
        pytest.root_url_portal = pytest.root_url

    # Register the custom distribution plugin defined above
    config.pluginmanager.register(XDistCustomPlugin())


def pytest_unconfigure(config):
    if not hasattr(config, "workerinput"):
        directory_path = TEST_DATA_PATH_OBJECT / "fence_clients"
        if os.path.exists(directory_path):
            shutil.rmtree(directory_path)
        if requires_fence_client_marker_present:
            setup.delete_all_fence_clients()
