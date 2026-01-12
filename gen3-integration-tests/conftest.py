import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import boto3
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
failed_test_suites = []


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
    if not hasattr(session.config, "workerinput"):
        for item in session.items:
            # Access the markers for each test item
            if (
                item.get_closest_marker("requires_fence_client")
                and not requires_fence_client_marker_present
            ):
                setup.setup_fence_test_clients_info()
                requires_fence_client_marker_present = True

            if (
                item.get_closest_marker("requires_google_bucket")
                and not requires_google_bucket_marker_present
            ):
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

    # Skip portal tests based on portal version
    config.skip_portal_tests = gat.skip_portal_tests()

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
    if (
        pytest.manifest.get("global", {}).get("frontend_root", "") == "gen3ff"
        and not config.skip_portal_tests
    ):
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
    # Is REGISTER_USERS_ON enabled
    pytest.is_register_user_enabled = gat.is_register_user_enabled(pytest.namespace)
    # Flag for identifying if root_url_portal is for frontend or not
    pytest.frontend_url = gat.is_frontend_url()
    if pytest.frontend_url:
        repo_name, branch_name, target_dir = gat.get_ff_commons_info()
        pytest.frontend_commons_name = target_dir
        if not hasattr(config, "workerinput"):
            gat.download_frontend_commons_app_repo(repo_name, branch_name, target_dir)
    # Register the custom distribution plugin defined above
    config.pluginmanager.register(XDistCustomPlugin())


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_logreport(report):
    yield

    if report.when != "call":
        return

    test_nodeid = report.nodeid
    start_time = datetime.fromtimestamp(report.start)
    message = {
        "run_date": str(start_time.date()),
        "repo_name": os.getenv("REPO"),
        "pr_num": os.getenv("PR_NUM"),
        "run_num": os.getenv("RUN_NUM"),
        "attempt_num": os.getenv("ATTEMPT_NUM"),
        "test_suite": test_nodeid.split("::")[1],
        "test_case": test_nodeid.split("::")[-1],
        "result": report.outcome,
        "duration": str(timedelta(seconds=report.duration)),
    }
    # Collect test suite failures for re-run
    if (
        report.outcome == "failed"
        and test_nodeid.split("::")[1] not in failed_test_suites
    ):
        failed_test_suites.append(test_nodeid.split("::")[1])
    # Add data to the queue
    try:
        sqs = boto3.client("sqs")
        queue_url = "https://sqs.us-east-1.amazonaws.com/707767160287/ci-metrics-sqs"
        response = sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(message))
        logger.info(f"[SQS MESSAGE SENT] MessageId: {response['MessageId']}")
    except Exception as e:
        logger.error(f"[SQS SEND ERROR] {e}")


def pytest_unconfigure(config):
    if pytest.frontend_url:
        ff_dir = Path(__file__).parent / pytest.frontend_commons_name
        shutil.rmtree(ff_dir, ignore_errors=True)
    # Skip running code if --collect-only is passed
    if config.option.collectonly:
        return
    if not hasattr(config, "workerinput"):
        directory_path = TEST_DATA_PATH_OBJECT / "fence_clients"
        if os.path.exists(directory_path):
            shutil.rmtree(directory_path)
        if requires_fence_client_marker_present:
            setup.delete_all_fence_clients()
        # Add failed test suites to GITHUB variable
        with open(os.getenv("GITHUB_ENV"), "a") as f:
            f.write(f"FAILED_TEST_SUITES={' or '.join(failed_test_suites)}")
        return
