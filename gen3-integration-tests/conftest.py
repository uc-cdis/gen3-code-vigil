import json
import os
import pytest

from pathlib import Path

from services.fence import Fence


def pytest_configure(config):
    # Compute hostname and namespace
    hostname = os.getenv("HOSTNAME")
    namespace = os.getenv("NAMESPACE")
    assert hostname or namespace
    if hostname and not namespace:
        namespace = hostname.split(".")[0]
    if namespace and not hostname:
        hostname = f"{namespace}.planx-pla.net"
    pytest.namespace = namespace

    # Compute root_url
    pytest.root_url = f"https://{hostname}"

    # Accounts used for testing
    pytest.users = {}
    pytest.users["main_account"] = "cdis.autotest@gmail.com"  # default user
    pytest.users["indexing_account"] = "ctds.indexing.test@gmail.com"  # indexing admin

    # Initialize auth headers
    pytest.auth_headers = {}

    # Save API key id's for cleanup
    pytest.api_key_ids = []


@pytest.fixture
def test_data_path():
    return Path(__file__).parent / "test_data"


# @pytest.fixture(autouse=True)
def compute_access_token_headers():
    fence = Fence()
    # Default user - main_account - cdis.autotest@gmail.com
    api_key_json = json.loads(
        (Path.home() / ".gen3" / f"{pytest.namespace}_main_account.json").read_text()
    )
    pytest.api_key_ids.append(api_key_json["key_id"])
    api_key = api_key_json["api_key"]
    access_token = fence.get_access_token(api_key)
    pytest.auth_headers["main_account"] = {
        "Accept": "application/json",
        "Authorization": f"bearer {access_token}",
        "Content-Type": "application/json",
    }
    # Indexing admin - indexing_account - ctds.indexing.test@gmail.com
    api_key_json = json.loads(
        (
            Path.home() / ".gen3" / f"{pytest.namespace}_indexing_account.json"
        ).read_text()
    )
    pytest.api_key_ids.append(api_key_json["key_id"])
    api_key = api_key_json["api_key"]
    access_token = fence.get_access_token(api_key)
    pytest.auth_headers["indexing_account"] = {
        "Accept": "application/json",
        "Authorization": f"bearer {access_token}",
        "Content-Type": "application/json",
    }
