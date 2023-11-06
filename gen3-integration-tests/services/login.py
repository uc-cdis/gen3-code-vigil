# Login Page:
# functions to login and log out on the environment

import re
import pytest
from playwright.sync_api import Page, expect


class Login(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}"
        self.LOGIN_URL = f"{self.BASE_URL}/login"

    def go_to_login_page(self, page: Page):
        """Goes to the login page"""
        page.goto(self.LOGIN_URL)
        nav_bar = page.locator("css=nav_bar")
        expect(nav_bar).to_be_visible

    def user_login(self, page: Page, user="main_account"):
        """Sets up Dev Cookie for main Account and logs in with Google
        Also checks if the access_token exists after login
        """
        page.context.add_cookies([{"name": "dev_login", "value": pytest.users[user]}])
        login_button = page.get_by_role(
            "button", name=re.compile("Google", re.IGNORECASE)
        )
        expect(login_button).to_be_visible()
        login_button.click()
        username = page.wait_for_selector("//div[@class='top-bar']//a[3]")
        assert (username.text) == pytest.users[user]
        cookies = page.context.cookies()
        for cookie in cookies:
            if cookie["name"] == "access_token":
                break

    def user_logout(self, page: Page):
        """Logs out and wait for Login button on nav bar"""
        page.get_by_role("button", name="Logout").click()
        nav_bar_login_button = page.get_by_role("button", name="Login")
        expect(nav_bar_login_button).to_be_visible

    # function to handle pop ups after login
    # def handle_popup(self, page: Page):
    #     """Handling popups after login"""
