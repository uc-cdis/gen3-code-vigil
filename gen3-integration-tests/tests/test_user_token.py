"""
USER TOKEN
"""

import pytest

from utils import logger
from pages.login import LoginPage
from services.fence import Fence
from utils.gen3_admin_tasks import create_access_token

from gen3.auth import Gen3Auth
from playwright.sync_api import Page
from urllib3.exceptions import ConnectionError


@pytest.mark.fence
class TestUserToken:
    fence = Fence()
    login_page = LoginPage()

    def test_create_api_key_success(self, page: Page):
        """
        Scenario: test create APIKey success
        Steps:
            1. Login using main_account user and get the access token.
            2. Create API Key using the access token.
            3. Verify api_key key is present in response from step 2.
            4. Delete the API Key
        """
        scope = ["data", "user"]

        # Login with main_account user and get the access_token
        logger.info("Logging in with mainAcct")
        self.login_page.go_to(page)
        access_token_cookie = self.login_page.login(page)

        # Create the api key using the access_token
        api_key_res = self.fence.create_api_key(
            scope=scope, token=access_token_cookie["value"]
        ).json()
        assert (
            "api_key" in api_key_res.keys()
        ), f"Expected api_key key but got {api_key_res}"

        # Delete the api key and logout
        self.fence.delete_api_key(
            api_key=api_key_res["key_id"], token=access_token_cookie["value"]
        )
        self.login_page.logout(page)

    def test_create_api_key_with_expired_access_token(self):
        """
        Scenario: create APIKey with expired access token
        Steps:
            1. Generate an expired access token.
            2. Create API Key using the access token.
            3. Validate the status code is 401 and
               "Authentication Error: Signature has expired"
               is present in the response from step 2.
        """
        fence_error_msg = "Authentication Error: Signature has expired"
        scope = ["data", "user"]

        # Generate expired access_token
        res = create_access_token(
            pytest.namespace, "fence", "1", "cdis.autotest@gmail.com"
        )
        access_token = res.splitlines()[-1].strip()

        # Create the api key using the access_token
        api_key_res = self.fence.create_api_key(scope=scope, token=access_token)
        assert (
            api_key_res.status_code == 401
        ), f"Expected 401 status but got {api_key_res.status_code}"
        if fence_error_msg not in api_key_res.content.decode():
            logger.error(f"{fence_error_msg} not found")
            logger.error(api_key_res.content.decode())
            raise

    def test_refresh_access_token_with_api_key(self, page: Page):
        """
        Scenario: refresh access token with apiKey
        Steps:
            1. Login using main_account user and get the access token.
            2. Create API Key using the access token.
            3. Verify api_key key is present in response from step 2.
            4. Refresh access token using the api key from step 2.
            5. Delete the API Key
        """
        scope = ["data", "user"]

        # Login with main_account user and get the access_token
        logger.info("Logging in with mainAcct")
        self.login_page.go_to(page)
        access_token_cookie = self.login_page.login(page)

        # Create the api key using the access_token
        api_key_res = self.fence.create_api_key(
            scope=scope, token=access_token_cookie["value"]
        ).json()

        # Generate access_token using the api_key
        auth = Gen3Auth(refresh_token=api_key_res, endpoint=f"{pytest.root_url}/user")
        auth.get_access_token()

        # Delete the api key and logout
        self.fence.delete_api_key(
            api_key=api_key_res["key_id"], token=access_token_cookie["value"]
        )
        self.login_page.logout(page)

    def test_refresh_access_token_with_invalid_api_key(self):
        """
        Scenario: refresh access token with invalid apiKey
        Steps:
            1. Refresh access token using an invalid api key.
            2. Expect "string indices must be integers" error from gen3sdk
        """
        gen3_sdk_error_msg = "string indices must be integers"

        # Refresh access token using invalid api_key
        auth = Gen3Auth(refresh_token="invalid", endpoint=f"{pytest.root_url}/user")
        try:
            auth.refresh_access_token()
        except Exception as e:
            exception_content = str(e)

        # Validate the response
        assert (
            gen3_sdk_error_msg == exception_content
        ), f"{gen3_sdk_error_msg} not found in response {exception_content}"

    def test_refresh_access_token_without_api_key(self):
        """
        Scenario: refresh access token without apiKey
        Steps:
            1. Refresh access token using no api key.
            2. Expect "Max retries exceeded" error from gen3sdk
        """
        gen3_sdk_error_msg = "Max retries exceeded"

        # Refresh access token using no api_key
        try:
            auth = Gen3Auth(refresh_token=None, endpoint=f"{pytest.root_url}/user")
            auth.refresh_access_token()
        except Exception as e:
            expection_content = str(e)

        # Validate the response
        assert (
            gen3_sdk_error_msg in expection_content
        ), f"{gen3_sdk_error_msg} not found in response {expection_content}"
