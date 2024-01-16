import json
import os
import pytest

from cdislogging import get_logger
from datasimulator.graph import Graph as DataSimGraph
from dictionaryutils import DataDictionary, dictionary
from pathlib import Path

from services.fence import Fence
from utils import TEST_DATA_PATH, gen3_admin_tasks

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
        print(f"API key file not found: '{file_path}'")
        raise
    pytest.api_keys["main_account"] = api_key_json
    api_key = api_key_json["api_key"]
    try:
        access_token = fence.get_access_token(api_key)
    except Exception as exc:
        print(f"Failed to get access token using API Key: {file_path}")
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
        print(f"API key file not found: '{file_path}'")
        raise
    pytest.api_keys["indexing_account"] = api_key_json
    api_key = api_key_json["api_key"]
    try:
        access_token = fence.get_access_token(api_key)
    except Exception as exc:
        print(f"Failed to get access token using API Key: {file_path}")
        raise
    pytest.auth_headers["indexing_account"] = {
        "Accept": "application/json",
        "Authorization": f"bearer {access_token}",
        "Content-Type": "application/json",
    }


@pytest.fixture(autouse=True, scope="session")
def setup_tests():
    get_configuration_files()
    generate_structured_data()


def get_configuration_files():
    """
    Get configuration files from the admin VM and save them at `test_data/configuration`
    """
    print("Creating configuration files")
    configs = gen3_admin_tasks.get_admin_vm_configurations(pytest.namespace)
    path = TEST_DATA_PATH / "configuration"
    path.mkdir(parents=True, exist_ok=True)
    for file_name, contents in configs.items():
        with (path / file_name).open("w", encoding="utf-8") as f:
            f.write(contents)


def generate_structured_data():
    """
    Most of the logic below is copied from data-simulator's `simulate` and `submission_order` commands.
    TODO: Move the logic to functions in `data-simulator` so we can import instead of duplicating code.
    """
    try:
        manifest = json.loads(
            (TEST_DATA_PATH / "configuration/manifest.json").read_text()
        )
    except FileNotFoundError:
        print(
            "manifest.json not found. It should have been fetched by `get_configuration_files`..."
        )
        raise

    dictionary_url = manifest.get("data", {}).get("dictionary_url")
    assert dictionary_url, "No dictionary URL in manifest.json"

    path = TEST_DATA_PATH / "structured_data"
    path.mkdir(parents=True, exist_ok=True)

    program = "jnkns"
    project = "jenkins"
    max_samples = 1  # the submission functions in services/structured_data.py assume there is only 1 record per node
    # TODO we should try setting `required_only` to False so the test data is more representative of real data
    required_only = True

    logger.info("Data simulator initialization...")
    logger.info("Loading dictionary from url {}".format(dictionary_url))
    dictionary.init(DataDictionary(url=dictionary_url))

    # Generate test data. Equivalent to running this command:
    # data-simulator simulate --url <dictionary_url> --path <test_data_path> --program jnkns --project jenkins
    logger.info("Initializing graph...")
    graph = DataSimGraph(dictionary, program=program, project=project)
    graph.generate_nodes_from_dictionary(consent_codes=True)
    graph.construct_graph_edges()

    # just print error messages
    graph.graph_validation(required_only=required_only)

    # simulate data whether the graph passes validation or not
    logger.info("Generating data...")
    graph.simulate_graph_data(
        path=path,
        n_samples=max_samples,
        node_num_instances_file=None,
        random=True,
        required_only=required_only,
        skip=True,
    )

    # Generate test data submission order. Equivalent to running this command:
    # data-simulator submission_order --url <dictionary_url> --path <test_data_path>
    # NOTE: not using `leaf_node` like in old gen3-qa tests... just generating everything.
    logger.info("Generating data submission order...")
    submission_order = graph.generate_submission_order()
    with open(os.path.join(path, "DataImportOrderPath.txt"), "w") as outfile:
        for node in submission_order:
            outfile.write(node.name + "\t" + node.category + "\n")
