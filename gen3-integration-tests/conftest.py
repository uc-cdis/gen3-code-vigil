import json
import os
import shutil
from pathlib import Path

import allure
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

        # Run all tests with marker ras to run serially (same worker)
        if node.get_closest_marker("ras"):
            return "__ras__"

        # Group all tests that affect ES indices and run them on the same worker serially
        if node.get_closest_marker("guppy") or node.get_closest_marker("pfb"):
            return "__indices__"

        # otherwise, each test is in its own scope
        return nodeid.rsplit("::", 1)[0]


def pytest_collection_finish(session):
    global requires_fence_client_marker_present
    global requires_google_bucket_marker_present
    # Skip running code if --collect-only is passed
    if session.config.option.collectonly:
        return
    # Iterate through the collected test items
    skip_portal_tests = session.config.skip_portal_tests
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
                if marker_name == "portal" and skip_portal_tests:
                    item.add_marker(
                        pytest.mark.skip(
                            reason="Skipping portal tests as non-supported portal is deployed"
                        )
                    )
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
        pytest.manifest = json.loads(
            (TEST_DATA_PATH_OBJECT / "configuration" / "manifest.json").read_text()
        )
    except FileNotFoundError:
        logger.error(
            "manifest.json not found. It should have been fetched by `get_configuration_files`..."
        )
        raise
    if pytest.manifest.get("global", {}).get("frontend_root", "") == "gen3ff":
        pytest.root_url_portal = f"https://{pytest.hostname}/portal"
    else:
        pytest.root_url_portal = pytest.root_url

    # List of services deployed
    pytest.deployed_services = gat.get_list_of_services_deployed()
    # List of sower jobs enabled
    pytest.enabled_sower_jobs = gat.get_enabled_sower_jobs()
    # # Is Flag enabled for USE_AGG_MDS
    pytest.use_agg_mdg_flag = gat.is_agg_mds_enabled()
    # Is indexs3client job deployed
    pytest.indexs3client_job_deployed = gat.check_indexs3client_job_deployed()
    pytest.google_enabled = gat.is_google_enabled()
    # Skip portal tests based on portal version
    config.skip_portal_tests = gat.skip_portal_tests()
    # Is REGISTER_USERS_ON enabled
    pytest.is_register_user_enabled = gat.is_register_user_enabled(pytest.namespace)
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


@pytest.fixture(scope="session", autouse=True)
def attach_combined_log_on_exit(request):
    def finalizer():
        logs_dir = Path("output")
        combined_log_path = logs_dir / "test_logs.log"
        worker_logs = sorted(logs_dir.glob("logs_*.log"))

        with open(combined_log_path, "w") as outfile:
            for log_file in worker_logs:
                outfile.write(f"\n--- Logs from {log_file.name} ---\n")
                with open(log_file) as infile:
                    outfile.write(infile.read())
                outfile.write("\n")

        with open(combined_log_path) as f:
            allure.attach(
                f.read(),
                name="Test Run Logs",
                attachment_type=allure.attachment_type.TEXT,
            )

    request.addfinalizer(finalizer)
