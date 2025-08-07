"""
Register User
"""

import os
import re

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
        pytest.users["skip_register_user"] = "skip-register-user@example.org"

    def test_user_login_failure_without_user_registration(self, page: Page):
        """
        Scenario: User login failure without user registration
        Steps:
            1. Perform login using skip_register_user
            2. Page should get redirected to /user/register
            3. Skip user registration and goto /explorer page
            4. User shouldn't be logged in
        """
        if not self.register_user_enabled:
            pytest.skip("RegisterUser is not enabled")
        # Login with skip_register_user
        self.login_page.go_to(page)
        # Don't perform user registration
        self.login_page.login(
            page, user="skip_register_user", skip_user_registeration=True
        )
        # Goto explorer page without user registration
        self.exploration.goto_explorer_page(page)
        # Verify user is not logged in
        username = page.locator("//*[text()]").filter(
            has_text=re.compile(pytest.users["skip_register_user"], re.IGNORECASE)
        )
        expect(username).not_to_be_visible()

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

        # Goto explorer page and click on download button
        self.exploration.click_on_download(page)
