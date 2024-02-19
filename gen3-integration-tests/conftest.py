import json
import os
import pytest

from cdislogging import get_logger
from datasimulator.main import (
    initialize_graph,
    run_simulation,
    run_submission_order_generation,
)
from pathlib import Path

from services.fence import Fence
from utils import TEST_DATA_PATH_OBJECT, gen3_admin_tasks
from utils.misc import one_worker_only

# Using dotenv to simplify setting up env vars locally
from dotenv import load_dotenv


load_dotenv()

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


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

    # Compute auth headers
    pytest.auth_headers = {}
    fence = Fence()
    pytest.api_keys = {}
    # Default user - main_account - cdis.autotest@gmail.com
    file_path = Path.home() / ".gen3" / f"{pytest.namespace}_main_account.json"
    try:
        api_key_json = json.loads(file_path.read_text())
    except FileNotFoundError:
        logger.error(f"API key file not found: '{file_path}'")
        raise
    pytest.api_keys["main_account"] = api_key_json
    api_key = api_key_json["api_key"]
    try:
        access_token = fence.get_access_token(api_key)
    except Exception as exc:
        logger.error(f"Failed to get access token using API Key: {file_path}")
        raise
    pytest.auth_headers["main_account"] = {
        "Accept": "application/json",
        "Authorization": f"bearer {access_token}",
        "Content-Type": "application/json",
    }
    # Indexing admin - indexing_account - ctds.indexing.test@gmail.com
    file_path = Path.home() / ".gen3" / f"{pytest.namespace}_indexing_account.json"
    try:
        api_key_json = json.loads(file_path.read_text())
    except FileNotFoundError:
        logger.error(f"API key file not found: '{file_path}'")
        raise
    pytest.api_keys["indexing_account"] = api_key_json
    api_key = api_key_json["api_key"]
    try:
        access_token = fence.get_access_token(api_key)
    except Exception as exc:
        logger.error(f"Failed to get access token using API Key: {file_path}")
        raise
    pytest.auth_headers["indexing_account"] = {
        "Accept": "application/json",
        "Authorization": f"bearer {access_token}",
        "Content-Type": "application/json",
    }


@pytest.fixture(autouse=True, scope="session")
@one_worker_only
def setup_tests():
    get_configuration_files()
    generate_graph_data()


def get_configuration_files():
    """
    Get configuration files from the admin VM and save them at `test_data/configuration`
    """
    logger.info("Creating configuration files")
    configs = gen3_admin_tasks.get_admin_vm_configurations(pytest.namespace)
    path = TEST_DATA_PATH_OBJECT / "configuration"
    path.mkdir(parents=True, exist_ok=True)
    for file_name, contents in configs.items():
        with (path / file_name).open("w", encoding="utf-8") as f:
            f.write(contents)


def generate_graph_data():
    """
    Call data-simulator functions to generate graph data for each node in the dictionary and to generate
    the submission order.
    """
    try:
        manifest = json.loads(
            (TEST_DATA_PATH_OBJECT / "configuration/manifest.json").read_text()
        )
    except FileNotFoundError:
        logger.error(
            "manifest.json not found. It should have been fetched by `get_configuration_files`..."
        )
        raise

    dictionary_url = manifest.get("data", {}).get("dictionary_url")
    assert dictionary_url, "No dictionary URL in manifest.json"

    data_path = TEST_DATA_PATH_OBJECT / "graph_data"
    data_path.mkdir(parents=True, exist_ok=True)

    program = "jnkns"
    project = "jenkins"
    max_samples = 1  # the submission functions in services/graph.py assume there is only 1 record per node
    # TODO we should try setting `required_only` to False so the test data is more representative of real data
    required_only = True

    graph = initialize_graph(
        dictionary_url=dictionary_url,
        program=program,
        project=project,
        consent_codes=True,
    )
    run_simulation(
        graph=graph,
        data_path=data_path,
        max_samples=max_samples,
        node_num_instances_file=None,
        random=True,
        required_only=required_only,
        skip=True,
    )
    # NOTE: not using a "leaf node" like in old gen3-qa tests... just generating everything.
    # Submission takes more time, but data is more representative of real data.
    run_submission_order_generation(graph=graph, data_path=data_path, node_name=None)

    logger.info("Done generating data:")
    for f_path in sorted(os.listdir(data_path)):
        with open(data_path / f_path, "r") as f:
            logger.info(f"{f_path}:\n{f.read()}")
