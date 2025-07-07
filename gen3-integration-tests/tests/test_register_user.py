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
from utils import gen3_admin_tasks as gat

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.skipif(
    "portal" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.skipif(
    "fence" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.portal
@pytest.mark.fence
class TestRegisterUser:
    @classmethod
    def setup_class(cls):
        cls.login_page = LoginPage()
        cls.user_register = UserRegister()
        cls.exploration = ExplorationPage()
        cls.register_user_enabled = gat.is_register_user_enabled(pytest.namespace)

        # Add new user to pytest.users
        pytest.users["register_user"] = "register-user@example.org"

    def test_redirect_to_login_page_from_the_download_button(self, page: Page):
        """
        Scenario: Redirect to login page from the download button
        Steps:
            1. Goto explorer page without logging in
            2. Click on download button
            3. Page should get rediected to /login page
        """
        if not self.register_user_enabled:
            pytest.skip("RegisterUser is not enabled")
        # Goto explorer page
        self.login_page.go_to(page)
        self.exploration.goto_explorer_page(page)

        # Click on download button
        self.exploration.click_on_login_to_download(page)

        # Verify page got redirected to /login page
        page.wait_for_load_state("load")
        current_url = page.url
        assert "/login" in current_url, f"Expected /login in url but got {current_url}"

    def test_redirect_to_register_page_after_login(self, page: Page):
        """
        Scenario: Redirect to register page after login and Download from /explorer page
        Steps:
            1. Perform login using register_user
            2. Page should get redirected to /user/register
            3. Fill the form to register user
            4. Goto /explorer page and perform download
        """
        if not self.register_user_enabled:
            pytest.skip("RegisterUser is not enabled")
        # Login with register_user
        self.login_page.go_to(page)
        self.login_page.login(
            page, user="register_user", validate_username_locator=False
        )
        accept_button = page.query_selector(self.login_page.POP_UP_ACCEPT_BUTTON)
        if accept_button:
            accept_button.click()

        # Goto explorer page
        self.exploration.goto_explorer_page(page)

        # Click on download button
        self.exploration.click_on_download(page)
