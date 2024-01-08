# Login Page
# functions to login and log out on the environment

import os
import re
import pytest
from playwright.sync_api import expect

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class LoginPage:
    def __init__(self, page):
        self.page = page
        # Endpoints
        self.BASE_URL = f"{pytest.root_url}"
        self.LOGIN_URL = f"{self.BASE_URL}/login"
        # Locators
        self.nav_bar = "//div[@class='nav-bar']"  # homepage navigation bar
        self.username_locator = "//div[@class='top-bar']//a[3]"  # username locator
        self.pop_up_box = "//div[@id='popup']"  # pop_up_box

    def go_to_page(self):
        """Goes to the login page"""
        self.page.goto(self.LOGIN_URL)
        self.page.wait_for_selector(self.nav_bar, state="visible")
        self.page.screenshot(path="output/LoginPage.png", full_page=True)

    def login(self, user="main_account"):
        """
        Sets up Dev Cookie for main Account and logs in with Google
        Also checks if the access_token exists after login
        """
        self.page.context.add_cookies(
            [{"name": "dev_login", "value": pytest.users[user], "url": self.LOGIN_URL}]
        )
        login_button = self.page.get_by_role(
            "button",
            name=re.compile(r"Login from Google", re.IGNORECASE),
        )
        """
        name=re.compile(
                r"Dev login - set username in 'dev_login' cookie", re.IGNORECASE
            ),
        """
        expect(login_button).to_be_visible(timeout=5000)
        login_button.click()
        self.page.wait_for_timeout(3000)
        self.page.screenshot(path="output/AfterLogin.png", full_page=True)
        self.page.wait_for_selector(self.username_locator, state="attached")

        self.handle_popup()
        self.page.screenshot(path="output/AfterPopUpAccept.png", full_page=True)
        access_token_cookie = next(
            (
                cookie
                for cookie in self.page.context.cookies()
                if cookie["name"] == "access_token"
            ),
            None,
        )
        assert (
            access_token_cookie is not None
        ), "Access token cookie not found after login"

    def logout(self):
        """Logs out and wait for Login button on nav bar"""
        self.page.get_by_role("button", name="Logout").click()
        nav_bar_login_button = self.page.get_by_role("button", name="Login")
        self.page.screenshot(path="output/AfterLogout.png")
        expect(nav_bar_login_button).to_be_visible

    # function to handle pop ups after login
    def handle_popup(self):
        """Handling popups after login"""
        popup_message = self.page.query_selector(self.pop_up_box)
        if popup_message:
            logger.info("Popup message found")
            self.page.evaluate(
                f"""
                (element) => {{
                    element.scrollTop = element.scrollHeight;
                }}
                """,
                popup_message,
            )
            self.page.screenshot(path="output/PopupBox.png")
            accept_button = self.page.get_by_role("button", name="Accept")
            if accept_button:
                accept_button.click()
        else:
            logger.info("Popup message not found")
