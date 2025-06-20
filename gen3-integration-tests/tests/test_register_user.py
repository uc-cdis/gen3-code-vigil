"""
Register User
"""

import os

import pytest
from cdislogging import get_logger
from pages.exploration import ExplorationPage
from pages.login import LoginPage
from pages.user_register import UserRegister
from playwright.sync_api import Page, expect

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.skipif(
    "portal" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.skipif(
    "fence" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.skipif(
    not pytest.is_register_user_enabled,
    reason="RegisterUser is not enabled",
)
@pytest.mark.portal
@pytest.mark.fence
class TestRegisterUser:
    @classmethod
    def setup_class(cls):
        cls.login_page = LoginPage()
        cls.user_register = UserRegister()
        cls.exploration = ExplorationPage()
        cls.user_email_id = "register-user@example.org"

    def test_redirect_to_login_page_from_the_download_button(self, page: Page):
        """
        Scenario: Redirect to login page from the download button
        Steps:
            1. Goto explorer page without logging in
            2. Click on download button
            3. Page should get rediected to /login page
        """
        # Goto explorer page
        self.login_page.go_to(page)
        self.exploration.goto_explorer_page(page)

        # Click on download button
        self.exploration.click_on_login_to_download(page)

        # Verify page got redirected to /login page
        expect(page.locator(self.login_page.LOGIN_BUTTON_LIST)).to_be_visible(
            timeout=10000
        )
        current_url = page.url
        assert "/login" in current_url, f"Expected /login in url but got {current_url}"

    def test_redirect_to_register_page_after_login(self, page: Page):
        """
        Scenario: Redirect to register page after login and Download from /explorer page
        Steps:
            1. Perform login using main_account
            2. Page should get redirected to /user/register
            3. Fill the form to register user
            4. Goto /explorer page and perform download
        """
        # Login with Main Account
        self.login_page.go_to(page)
        self.login_page.login(page, validate_username_locator=False)

        # Goto explorer page
        self.exploration.goto_explorer_page(page)

        # Click on download button
        self.exploration.click_on_download(page)
