import json
import os
import pytest

from pathlib import Path

from services.fence import Fence


def pytest_configure(config):
    # Compute hostname
    hostname = os.getenv("HOSTNAME")
    assert hostname

    # Compute namespace
    namespace = os.getenv("NAMESPACE")
    if namespace:
        pytest.namespace = namespace
    else:
        pytest.namespace = hostname.split(".")[0]

    # Compute root_url
    pytest.root_url = f"https://{hostname}"

    # Compute auth header for default user - cdis.autotest@gmail.com
    fence = Fence()
    api_key = json.loads(
        (Path.home() / ".gen3" / f"{pytest.namespace}.json").read_text()
    )["api_key"]
    access_token = fence.get_access_token(api_key)
    pytest.auth_header = {
        "Accept": "application/json",
        "Authorization": f"bearer {access_token}",
        "Content-Type": "application/json",
    }


@pytest.fixture
def test_data_path():
    return Path(__file__).parent / "test_data"
