"""
Register User
"""

import os
import pytest

from pages.login import LoginPage
from pages.user_register import UserRegister
from utils.gen3_admin_tasks import (
    fence_enable_register_users_redirect,
    fence_disable_register_users_redirect,
)

from playwright.sync_api import Page, expect
from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


# TODO: This suite needs to run at the last since fence changes are needed
#       and will alter the login rediection to /user/register.
#       Need to implement the code for it.
@pytest.mark.portal
@pytest.mark.fence
@pytest.mark.skip("MIRDC Test case needs Register user redirect enabled on fence")
class TestRegisterUser:
    login_page = LoginPage()
    user_register = UserRegister()

    @classmethod
    def setup_class(cls):
        # Enable Register User Redirect Login
        fence_enable_register_users_redirect(test_env_namespace=pytest.namespace)

    @classmethod
    def teardown_class(cls):
        # Enable Register User Redirect Login
        fence_disable_register_users_redirect(test_env_namespace=pytest.namespace)

    @pytest.mark.skip("MIRDC Test case needs Register user redirect enabled on fence")
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
        self.user_register.goto_explorer_page(page)

        # Click on download button
        self.user_register.click_on_download(page)

        # Verify page got redirected to /login page
        expect(page.locator(self.login_page.LOGIN_BUTTON_LIST)).to_be_visible(
            timeout=10000
        )
        current_url = page.url
        assert "/login" in current_url, f"Expected /login in url but got {current_url}"

    @pytest.mark.skip("MIRDC Test case needs Register user redirect enabled on fence")
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

        # Register User
        self.user_register.register_user(page)

        # Goto explorer page
        self.user_register.goto_explorer_page(page)

        # Click on download button
        self.user_register.click_on_download(page)
