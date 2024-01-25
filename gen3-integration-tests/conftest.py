import json
import os
import pytest

from pathlib import Path

from services.fence import Fence
from utils import gen3_admin_tasks

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

    # Compute auth headers
    pytest.auth_headers = {}
    fence = Fence()
    # Save API key id's for cleanup
    pytest.api_key_ids = []
    # Default user - main_account - cdis.autotest@gmail.com
    file_path = Path.home() / ".gen3" / f"{pytest.namespace}_main_account.json"
    try:
        api_key_json = json.loads(file_path.read_text())
    except FileNotFoundError:
        print(f"API key file not found: '{file_path}'")
        raise
    pytest.api_key_ids.append(api_key_json["key_id"])
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
    pytest.api_key_ids.append(api_key_json["key_id"])
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
def get_configuration_files():
    """
    Get configuration files from the admin VM and save them at `test_data/configuration`
    """
    print("Creating configuration files")
    configs = gen3_admin_tasks.get_admin_vm_configurations(pytest.namespace)
    path = Path(__file__).parent / "test_data/configuration"
    path.mkdir(parents=True, exist_ok=True)
    for file_name, contents in configs.items():
        with (path / file_name).open("w", encoding="utf-8") as f:
            f.write(contents)


@pytest.fixture
def test_data_path():
    """Fixture to be used when a test needs test data"""
    return Path(__file__).parent / "test_data"
