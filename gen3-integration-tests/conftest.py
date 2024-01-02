import json
import os
import pytest
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright


from pathlib import Path

from services.fence import Fence


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

    # Compute root_url
    pytest.root_url = f"https://{hostname}"

    # Accounts used for testing
    pytest.users = {}
    pytest.users["main_account"] = "cdis.autotest@gmail.com"  # default user
    pytest.users["indexing_account"] = "ctds.indexing.test@gmail.com"  # indexing admin

    # Compute auth headers
    pytest.auth_headers = {}
    fence = Fence()
    # Save API key id's for cleanup
    pytest.api_key_ids = []
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


@pytest.fixture
def test_data_path():
    """Fixture to be used when a test needs test data"""
    return Path(__file__).parent / "test_data"


# Synchronous fixture for Playwright
@pytest.fixture
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()  # Create a new page
        yield page
        browser.close()


# Asynchronous fixture for Playwright
@pytest.fixture
async def async_browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()  # Create a new page asynchronously
        yield page
        await browser.close()
