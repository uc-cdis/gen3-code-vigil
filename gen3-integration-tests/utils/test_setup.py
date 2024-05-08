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
from services.graph import GraphDataTools
from utils import TEST_DATA_PATH_OBJECT, gen3_admin_tasks

from gen3.auth import Gen3Auth

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def get_api_key_and_auth_header(user):
    fence = Fence()
    file_path = Path.home() / ".gen3" / f"{pytest.namespace}_{user}.json"
    try:
        api_key_json = json.loads(file_path.read_text())
    except FileNotFoundError:
        logger.error(f"API key file not found: '{file_path}'")
        raise
    api_key = api_key_json["api_key"]
    try:
        access_token = fence.get_access_token(api_key)
    except Exception:
        logger.error(f"Failed to get access token using API Key: {file_path}")
        raise
    auth_header = {
        "Accept": "application/json",
        "Authorization": f"bearer {access_token}",
        "Content-Type": "application/json",
    }
    return (api_key_json, auth_header)


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
    required_only = False

    graph = initialize_graph(
        dictionary_url=dictionary_url,
        program=program,
        project=project,
        consent_codes=False,
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
            logger.debug(f"{f_path}:\n{f.read()}")


def create_program_project(user="main_account"):
    """
    Creates program and project if not present already
    """
    auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
    sd_tools = GraphDataTools(auth=auth, program_name="jnkns", project_code="jenkins")
    sd_tools.create_program_and_project()
