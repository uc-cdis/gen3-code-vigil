import pytest
from playwright.sync_api import Page, expect
from utils import logger
from utils.test_execution import screenshot


class UserRegister(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url_portal}/login"
        self.EXPLORER_ENDPOINT = f"{pytest.root_url_portal}/explorer"
        self.REGISTER_ENDPOINT = f"{pytest.root_url_portal}/user/register/"
        # Locators
        self.REGISTER_BUTTON = "//button[contains(text(),'Register')]"
        self.FIRST_NAME_INPUT = "//input[@id='firstname']"
        self.LAST_NAME_INPUT = "//input[@id='lastname']"
        self.ORGANIZATION_INPUT = "//input[@id='organization']"
        self.EMAIL_INPUT = "//input[@id='email']"

    def register_user(self, page, user_email):
        # Wait for the Register button to show up after login
        register_button = page.locator(self.REGISTER_BUTTON)
        expect(register_button).to_be_visible(timeout=10000)

        # Fill out the form and click on Register button
        page.locator(self.FIRST_NAME_INPUT).fill(user_email.split(".")[0])
        page.locator(self.LAST_NAME_INPUT).fill(user_email.split(".")[1])
        page.locator(self.ORGANIZATION_INPUT).fill("UChicago")
        if page.locator(self.EMAIL_INPUT).is_visible():
            page.locator(self.EMAIL_INPUT).fill(user_email)
        register_button.click()
