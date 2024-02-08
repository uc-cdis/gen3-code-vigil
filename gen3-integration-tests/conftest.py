import os
import pytest

from utils import test_setup as setup

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
<<<<<<< HEAD
    pytest.auth_headers = {}
    for user in pytest.users:
        (
            pytest.api_keys[user],
            pytest.auth_headers[user],
        ) = setup.get_api_key_and_auth_header(user)
=======
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
    # user0 dcf_integration_test - test user
    file_path = Path.home() / ".gen3" / f"{pytest.namespace}_user0_account.json"
    try:
        api_key_json = json.loads(file_path.read_text())
    except FileNotFoundError:
        print(f"API key file not found: '{file_path}'")
        raise
    pytest.api_keys["dcf_integration_user"] = api_key_json
    api_key = api_key_json["api_key"]
    try:
        access_token = fence.get_access_token(api_key)
    except Exception as exc:
        print(f"Failed to get access token using API Key: {file_path}")
        raise
    pytest.auth_headers["dcf_integration_user"] = {
        "Accept": "application/json",
        "Authorization": f"bearer {access_token}",
        "Content-Type": "application/json",
    }
>>>>>>> c14a693 (add jenkins jobs to run fence-create command)

    # Get configuration files
    setup.get_configuration_files()

    # Generate test data
    setup.generate_graph_data()