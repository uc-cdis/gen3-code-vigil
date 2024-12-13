import json
import os
import shutil

import pytest

# Using dotenv to simplify setting up env vars locally
from dotenv import load_dotenv
from utils import TEST_DATA_PATH_OBJECT
from utils import gen3_admin_tasks as gat
from utils import logger
from utils import test_setup as setup
from xdist import is_xdist_controller
from xdist.scheduler import LoadScopeScheduling

load_dotenv()
requires_fence_client_marker_present = False
requires_google_bucket_marker_present = False

collect_ignore = ["test_setup.py", "gen3_admin_tasks.py"]


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

        # otherwise, each test is in its own scope
        return nodeid.rsplit("::", 1)[0]


def pytest_collection_finish(session):
    global requires_fence_client_marker_present
    global requires_google_bucket_marker_present
    # Skip running code if --collect-only is passed
    if session.config.option.collectonly:
        return
    # Iterate through the collected test items
    if not hasattr(session.config, "workerinput"):
        for item in session.items:
            # Access the markers for each test item
            markers = item.keywords
            for marker_name, marker in markers.items():
                if (
                    marker_name == "requires_fence_client"
                    and requires_fence_client_marker_present is False
                ):
                    setup.setup_fence_test_clients_info()
                    requires_fence_client_marker_present = True
                if (
                    marker_name == "requires_google_bucket"
                    and requires_google_bucket_marker_present is False
                ):
                    # Create and Link Google Test Buckets
                    setup.setup_google_buckets()
                    requires_google_bucket_marker_present = True
        # Run Usersync job
        setup.run_usersync()


@pytest.fixture(scope="session", autouse=True)
def get_fence_clients():
    setup.get_client_id_secret()
    setup.get_rotated_client_id_secret()


def pytest_configure(config):
    # Compute hostname and namespace
    pytest.hostname = os.getenv("HOSTNAME")
    pytest.namespace = os.getenv("NAMESPACE")
    pytest.tested_env = os.getenv("TESTED_ENV")
    assert pytest.hostname or pytest.namespace, "Hostname and namespace undefined"
    if pytest.namespace and not pytest.hostname:
        pytest.hostname = f"{pytest.namespace}.planx-pla.net"
    if pytest.hostname and not pytest.namespace:
        pytest.namespace = gat.get_kube_namespace(pytest.hostname)
    # TODO: tested_env will differ from namespace for manifest PRs
    if not pytest.tested_env:
        pytest.tested_env = pytest.namespace
    # Compute root_url
    pytest.root_url = f"https://{pytest.hostname}"

    # Clients used for testing
    pytest.clients = {}
    pytest.rotated_clients = {}
    # Accounts used for testing
    pytest.users = setup.get_users()

    # Generate api key and auth headers
    pytest.api_keys = {}
    for user in pytest.users:
        pytest.api_keys[user] = setup.get_api_key(user)

    # Prevent pytest-xdist from running this on each worker individually
    if not hasattr(config, "workerinput"):
        # Get configuration files
        setup.get_configuration_files()

    # Compute root url for portal
    try:
        manifest = json.loads(
            (TEST_DATA_PATH_OBJECT / "configuration" / "manifest.json").read_text()
        )
    except FileNotFoundError:
        logger.error(
            "manifest.json not found. It should have been fetched by `get_configuration_files`..."
        )
        raise
    logger.info(manifest)
    if manifest.get("global", {}).get("frontend_root", "") == "gen3ff":
        pytest.root_url_portal = f"https://{pytest.hostname}/portal"
    else:
        pytest.root_url_portal = pytest.root_url

    # Register the custom distribution plugin defined above
    config.pluginmanager.register(XDistCustomPlugin())


def pytest_unconfigure(config):
    # Skip running code if --collect-only is passed
    if config.option.collectonly:
        return
    if not hasattr(config, "workerinput"):
        directory_path = TEST_DATA_PATH_OBJECT / "fence_clients"
        if os.path.exists(directory_path):
            shutil.rmtree(directory_path)
        if requires_fence_client_marker_present:
            setup.delete_all_fence_clients()


def pytest_runtest_logreport(report):
    status = ""
    if os.getenv("CI_METRICS_DB_HOST"):
        if report.when == "call":
            status = (
                "PASSED" if report.passed else "FAILED" if report.failed else "SKIPPED"
            )
            try:
                test_suite = report.nodeid.split("::")[-1]
                test_case = report.nodeid.split("::")[-2]
            except IndexError:
                test_suite = "N/A"
                test_case = "N/A"
            logger.info(
                f"## RUN LOG: {os.environ.get('REPO')} {os.environ.get('PR_NUM')} {os.environ.get('RUN_NUM')} {report.nodeid} {report.fspath} {status} {report.duration}"
            )
