# Login Page
# functions to login and log out on the environment

import os
import re
import pytest
from playwright.sync_api import Page, expect

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Login(object):
    def __init__(self):
        # Endpoints
        self.BASE_URL = f"{pytest.root_url}"
        self.LOGIN_URL = f"{self.BASE_URL}/login"
        # Locators
        self.nav_bar = ".nav_bar"  # homepage navigation bar
        self.username_locator = "//div[@class='top-bar']//a[3]"  # username locator
        self.pop_up_box = ".pop_up_box"  # pop_up_box

    def go_to_login_page(self, page: Page):
        """Goes to the login page"""
        page.goto(self.LOGIN_URL)
        expect(page.locator(self.nav_bar)).to_be_visible

    def user_login(self, page: Page, user="main_account"):
        """Sets up Dev Cookie for main Account and logs in with Google
        Also checks if the access_token exists after login
        """
        page.context.add_cookies([{"name": "dev_login", "value": pytest.users[user]}])
        login_button = page.get_by_role(
            "button", name=re.compile("Dev login", re.IGNORECASE)
        )
        expect(login_button).to_be_visible()
        login_button.click()
        page.screenshot(path="Afterlogin.png")
        username = page.wait_for_selector(self.username_locator)
        assert (username.text) == pytest.users[user]
        cookies = page.context.cookies()
        for cookie in cookies:
            if cookie["name"] == "access_token":
                break

    def user_logout(self, page: Page):
        """Logs out and wait for Login button on nav bar"""
        page.get_by_role("button", name="Logout").click()
        nav_bar_login_button = page.get_by_role("button", name="Login")
        page.screenshot(path="Afterlogout.png")
        expect(nav_bar_login_button).to_be_visible

    # function to handle pop ups after login
    def handle_popup(self, page: Page):
        """Handling popups after login"""
        popup_message = page.query_selector(self.pop_up_box)
        if popup_message:
            page.screenshot(path="popupBox.png", full_page=True)
            logger.info("Popup message found")
            accept_button = page.get_by_role("button", name="Accept")
            if accept_button:
                accept_button.click()
        else:
            logger.info("Popup message not found")
