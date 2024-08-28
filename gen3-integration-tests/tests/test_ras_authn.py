"""
RAS AuthN
"""

import os
import pytest

from services.fence import Fence
from pages.login import LoginPage

from cdislogging import get_logger
from playwright.sync_api import Page

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.portal
@pytest.mark.fence
class TestRasAuthN:
    fence = Fence()
    login_page = LoginPage()

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
        self.login_page.go_to(page)
        self.login_page.ras_login(
            page,
            username=os.environ["CI_TEST_RAS_USERID"],
            password="THIS_IS_AN_INVALID_PASSWORD_FOR_USER_1",
        )
        html_content = page.content()
        assert (
            "Access Denied" in html_content
        ), f"Expected Access Denied but got {html_content}"
