"""
Register User
"""

import os
import pytest

from services.indexd import Indexd
from services.fence import Fence
from pages.login import LoginPage
from utils.test_execution import screenshot

from playwright.sync_api import Page, expect
from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.portal
@pytest.mark.fence
class TestRegisterUser:
    login_page = LoginPage()
    REGISTER_BUTTON = "//button[@type='submit']"
    FIRST_NAME_INPUT = "//input[@id='firstname']"
    LAST_NAME_INPUT = "//input[@id='lastname']"
    ORGANIZATION_INPUT = "//input[@id='organization']"
    USERNAME_LOCATOR = "//div[@class='top-bar']//a[3]"
    EXPLORER_ENDPOINT = f"{pytest.root_url_portal}/explorer"
    REGISTER_ENDPOINT = f"{pytest.root_url_portal}/user/register/"
    DOWNLOAD_BUTTON = '//button[contains(text(),"Download")][position()=1]'
    DROPDOWN_ITEM = '//button[@class=" g3-dropdown__item "]'

    def test_redirect_to_register_page_after_login(self, page: Page):
        """
        Scenario: Redirect to register page after login
        Steps:
            1.
        """
        # Login with Main Account
        self.login_page.go_to(page)
        self.login_page.login(page, validate_username_locator=False)

        # NOTE: This is just for testing purpose and needs to be removed at the end
        page.goto(self.REGISTER_ENDPOINT)

        # Wait for the Register button to show up after login
        register_button = page.locator(self.REGISTER_BUTTON)
        expect(register_button).to_be_visible(timeout=5000)

        # Get the current url and validate the endpoint
        current_url = page.url
        assert (
            "/user/register" in current_url
        ), f"Expected /user/register in url but got {current_url}"

        # Fill out the form and click on Register button
        page.locator(self.FIRST_NAME_INPUT).fill("Cdis")
        page.locator(self.LAST_NAME_INPUT).fill("Test")
        page.locator(self.ORGANIZATION_INPUT).fill("Uchicago")
        register_button.click()

        # Wait for USERNAME_LOCATOR to showup
        page.wait_for_selector(self.USERNAME_LOCATOR, state="attached")

        # Goto explorer page
        page.goto(self.EXPLORER_ENDPOINT)

        # Click on Download button
        download_button = page.locator(self.DOWNLOAD_BUTTON)
        expect(download_button).to_be_visible(timeout=5000)
        download_button.click()

        # Click on Dropdown item
        dropdown_item = page.locator(self.DROPDOWN_ITEM)
        dropdown_item.click()
