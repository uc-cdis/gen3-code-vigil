"""
RAS AuthN
"""

import os
import pytest

from cdislogging import get_logger
from services.fence import Fence
from pages.login import LoginPage
from playwright.sync_api import Page, expect

from utils.test_execution import screenshot

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.portal
@pytest.mark.fence
@pytest.mark.requires_fence_client
class TestRasAuthN:
    fence = Fence()
    login_page = LoginPage()

    @classmethod
    def setup_class(cls):
        # Confirm CI_TEST_RAS_USERID and CI_TEST_RAS_PASSWORD are present in env
        assert "CI_TEST_RAS_USERID" in os.environ, "CI_TEST_RAS_USERID not found"
        assert "CI_TEST_RAS_PASSWORD" in os.environ, "CI_TEST_RAS_PASSWORD not found"

        # Get the client id for CI_TEST_RAS_USERID
        cls.basic_test_ras_client_id, cls.basic_test_ras_client_secret = (
            cls.fence.get_client_id_secret(client_name="ras-test-client")
        )

        # URL for RAS Login Page
        cls.url = f"""{pytest.root_url_portal}/user/oauth2/authorize?
        response_type=code&client_id={cls.basic_test_ras_client_id}&
        redirect_uri={pytest.root_url_portal}/user&scope=openid+user+
        data+google_credentials+ga4gh_passport_v1&idp=ras"""

    def test_provide_invalid_credentials_NIH_login_page(self, page: Page):
        """
        Scenario: Provide invalid credentials in NIH Login page
        Steps:
            1. Create a RAS test client and get its client_id.
            2. Use the RAS Login url generated using the client_id.
            3. Provide an invalid password to login.
            4. Verify 'Access Denied' is visible on page.
        NOTE : This test requires CI_TEST_RAS_ID & CI_TEST_RAS_PASSWORD
        secrets to be configured with RAS credentials
        """
        page.goto(self.url)
        ras_login_button = page.locator(self.login_page.RAS_LOGIN_BUTTON)
        expect(ras_login_button).to_be_visible(timeout=5000)
        page.locator(self.login_page.RAS_USERNAME_INPUT).fill(
            os.environ["CI_TEST_RAS_USERID"]
        )
        page.locator(self.login_page.RAS_PASSWORD_INPUT).fill(
            "THIS_IS_AN_INVALID_PASSWORD_FOR_USER"
        )
        screenshot(page, "BeforeRASLogin")
        ras_login_button.click()
        screenshot(page, "AfterRASLogin")
        html_content = page.content()
        assert (
            "Access Denied" in html_content
        ), f"Expected Access Denied but got {html_content}"
