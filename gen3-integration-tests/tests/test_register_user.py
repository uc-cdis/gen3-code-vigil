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
from utils.test_execution import screenshot

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.skipif(
    "fence" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.portal
@pytest.mark.frontend_framework
@pytest.mark.fence
@pytest.mark.skipif(
    pytest.frontend_url,
    reason="loginForDownload button functionality on Exploration page is not working (GFF-519)",
)
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
        # Don't perform user registration
        self.login_page.go_to(page)
        self.login_page.login(
            page, user="skip_register_user", skip_user_registeration=True
        )

        # Goto explorer page and click on download button
        self.exploration.click_on_download(
            page, locator_element=self.exploration.LOGIN_TO_DOWNLOAD_BUTTON
        )

        # Verify page got redirected to /login page
        page.wait_for_load_state("load")
        current_url = page.url.lower()
        screenshot(page, "AfterLoginToDownloadRedirect")
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

        # Goto explorer page and click on download button
        self.exploration.click_on_download(
            page, locator_element=self.exploration.DOWNLOAD_BUTTON
        )
        self.login_page.logout(page)
