"""
Logn Page
"""

import os

import pytest
from cdislogging import get_logger
from pages.login import LoginPage
from playwright.sync_api import Page, expect
from utils.test_execution import screenshot

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.portal
class TestLoginPage:
    @classmethod
    def setup_class(cls):
        cls.login_page = LoginPage()
        if pytest.frontend_url:
            cls.WORKSPACE_URL = f"{pytest.root_url_portal}/Workspace"
        else:
            cls.WORKSPACE_URL = f"{pytest.root_url_portal}/workspace"
        cls.QUERY_PARAM_URL = (
            f"{pytest.root_url_portal}/DEV-test/search?node_type=summary_clinical"
        )

    def test_login_redirects_to_requested_page(self, page: Page):
        """
        Scenario: Login redirects to requested page
        Steps:
            1. Use the workspace url to goto /workspace page without logging in
            2. Page should get redirected to /login page
            3. Login using main_account
            4. After login, page should directly goto /workspace page
        """
        self.login_page.go_to(page=page, url=self.WORKSPACE_URL)

        # Should be redirected to login page
        screenshot(page, "RedirectPage")
        page.get_by_text(self.login_page.GEN3_ORCID_LOGIN_BUTTON).wait_for(
            state="visible", timeout=10000
        )
        screenshot(page, "RedirectPage")
        current_url = page.url.lower()
        assert "/login" in current_url, f"Expected /login in url but got {current_url}"

        # Perform user login
        self.login_page.login(page)

        # Validate the user is redirected to workspace page after logging in
        current_url = page.url.lower()
        assert (
            "/workspace" in current_url
        ), f"Expected /workspace in url but got {current_url}"

        self.login_page.logout(page)

    def test_login_redirects_to_requested_page_with_query_params_intact(
        self, page: Page
    ):
        """
        Scenario: Login redirects to requested page
        Steps:
            1. Use the query params url to goto /DEV-test/search?node_type=summary_clinical page without logging in
            2. Page should get redirected to /login page
            3. Login using main_account
            4. After login, page should directly goto /DEV-test/search?node_type=summary_clinical page
        """
        self.login_page.go_to(page=page, url=self.QUERY_PARAM_URL)

        # Should be redirected to login page
        screenshot(page, "RedirectPage")
        page.get_by_text(self.login_page.GEN3_ORCID_LOGIN_BUTTON).wait_for(
            state="visible", timeout=10000
        )
        screenshot(page, "RedirectPage")
        current_url = page.url
        assert "/login" in current_url, f"Expected /login in url but got {current_url}"

        # Perform user login
        self.login_page.login(page)

        # Validate the user is redirected to workspace page after logging in
        current_url = page.url
        assert (
            "/DEV-test/search" in current_url
        ), f"Expected /DEV-test/search in url but got {current_url}"

        self.login_page.logout(page)
