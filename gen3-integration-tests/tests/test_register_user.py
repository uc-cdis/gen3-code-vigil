"""
Register User
"""

import os
import pytest

from pages.login import LoginPage
from utils.test_execution import screenshot
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
    REGISTER_BUTTON = "//button[@type='submit']"
    FIRST_NAME_INPUT = "//input[@id='firstname']"
    LAST_NAME_INPUT = "//input[@id='lastname']"
    ORGANIZATION_INPUT = "//input[@id='organization']"
    EMAIL_INPUT = "//input[@id='email']"
    EXPLORER_ENDPOINT = f"{pytest.root_url_portal}/explorer"
    REGISTER_ENDPOINT = f"{pytest.root_url_portal}/user/register/"
    ACCEPT_BUTTON = "//button[text()='Accept']"
    DOWNLOAD_BUTTON = '//button[contains(text(),"Download")][position()=1]'
    LOGIN_TO_DOWNLOAD_BUTTON = "//button[normalize-space()='Login to download table']"
    EXPLORATION_BUTTON = "//a[normalize-space()='Exploration']"
    LOGIN_TO_DOWNLOAD_LIST_FIRST_ITEM = (
        '//*[contains(@class, " g3-dropdown__item ")][1]'
    )

    @classmethod
    def setup_class(cls):
        # Enable Register User Redirect Login
        fence_enable_register_users_redirect(pytest.namespace)

    @classmethod
    def teardown_class(cls):
        # Enable Register User Redirect Login
        fence_disable_register_users_redirect(pytest.namespace)

    @pytest.mark.skip("MIRDC Test case needs Register user redirect enabled on fence")
    def test_redirect_to_login_page_from_the_download_button(self, page: Page):
        """
        Scenario: Redirect to login page from the download button
        Steps:
            1.
        """
        self.login_page.go_to(page)
        page.locator(self.EXPLORATION_BUTTON).click()
        screenshot(page, "ExplorerPage")

        # Verify /explorer page is loaded
        expect(page.locator(self.login_page.USERNAME_LOCATOR)).to_be_visible(
            timeout=10000
        )
        current_url = page.url
        assert (
            "/explorer" in current_url
        ), f"Expected /explorer in url but got {current_url}"

        # Click on the Download Button
        download_button = page.locator(self.LOGIN_TO_DOWNLOAD_BUTTON)
        assert download_button.is_enabled()
        download_button.click()
        screenshot(page, "AfterClickingDownload")

        # Click on the file type to download
        login_to_download_list_first_item = page.locator(
            self.LOGIN_TO_DOWNLOAD_LIST_FIRST_ITEM
        )
        login_to_download_list_first_item.wait_for(state="visible", timeout=10000)
        login_to_download_list_first_item.click()

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

        # Wait for the Register button to show up after login
        register_button = page.locator(self.REGISTER_BUTTON)
        expect(register_button).to_be_visible(timeout=10000)

        # Get the current url and validate the endpoint
        current_url = page.url
        assert (
            "/user/register" in current_url
        ), f"Expected /user/register in url but got {current_url}"

        # Fill out the form and click on Register button
        page.locator(self.FIRST_NAME_INPUT).fill("Cdis")
        page.locator(self.LAST_NAME_INPUT).fill("Test")
        page.locator(self.ORGANIZATION_INPUT).fill("Uchicago")
        if page.locator(self.EMAIL_INPUT).is_visible():
            page.locator(self.EMAIL_INPUT).fill("cdis.autotest@gmail.com")
        register_button.click()

        # Wait for username to showup
        accept_button = page.locator(self.ACCEPT_BUTTON)
        if accept_button.is_visible(timeout=5000):
            accept_button.click()
        screenshot(page, "AfterRegisteringUser")
        expect(page.locator(self.login_page.USERNAME_LOCATOR)).to_be_visible(
            timeout=10000
        )

        # Goto explorer page
        page.goto(self.EXPLORER_ENDPOINT)
        screenshot(page, "ExplorerPage")

        # Click on Download button
        download_button = page.locator(self.DOWNLOAD_BUTTON)
        expect(download_button).to_be_visible(timeout=5000)
        download_button.click()
