import pytest
from playwright.sync_api import Page, expect
from utils.test_execution import screenshot


class UserRegister(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url_portal}/login"
        self.EXPLORER_ENDPOINT = f"{pytest.root_url_portal}/explorer"
        self.REGISTER_ENDPOINT = f"{pytest.root_url_portal}/user/register/"
        # Locators
        self.REGISTER_BUTTON = "//button[@type='submit']"
        self.FIRST_NAME_INPUT = "//input[@id='firstname']"
        self.LAST_NAME_INPUT = "//input[@id='lastname']"
        self.ORGANIZATION_INPUT = "//input[@id='organization']"
        self.EMAIL_INPUT = "//input[@id='email']"
        self.ACCEPT_BUTTON = "//button[text()='Accept']"
        self.DOWNLOAD_BUTTON = '//button[contains(text(),"Download")][position()=1]'
        self.LOGIN_TO_DOWNLOAD_BUTTON = (
            "//button[normalize-space()='Login to download table']"
        )
        self.EXPLORATION_BUTTON = "//a[normalize-space()='Exploration']"
        self.USERNAME_LOCATOR = "//div[@class='top-bar']//a[3]"
        self.LOGIN_TO_DOWNLOAD_LIST_FIRST_ITEM = (
            '//*[contains(@class, " g3-dropdown__item ")][1]'
        )

    def register_user(self, page: Page, user_email: str):
        # Wait for the Register button to show up after login
        register_button = page.locator(self.REGISTER_BUTTON)
        expect(register_button).to_be_visible(timeout=10000)

        # Get the current url and validate the endpoint
        current_url = page.url
        assert (
            "/user/register" in current_url
        ), f"Expected /user/register in url but got {current_url}"

        # Fill out the form and click on Register button
        first_name = user_email.split("@")[0].split(".")[0]
        last_name = user_email.split("@")[0].split(".")[1]
        page.locator(self.FIRST_NAME_INPUT).fill(first_name)
        page.locator(self.LAST_NAME_INPUT).fill(last_name)
        page.locator(self.ORGANIZATION_INPUT).fill("UChicago")
        if page.locator(self.EMAIL_INPUT).is_visible():
            page.locator(self.EMAIL_INPUT).fill(user_email)
        register_button.click()

        # Wait for username to showup
        accept_button = page.locator(self.ACCEPT_BUTTON)
        if accept_button.is_visible(timeout=5000):
            accept_button.click()
        screenshot(page, "AfterRegisteringUser")
        expect(page.locator(self.USERNAME_LOCATOR)).to_be_visible(timeout=10000)

    def goto_explorer_page(self, page):
        # Goto explorer page
        page.goto(self.EXPLORER_ENDPOINT)
        screenshot(page, "ExplorerPage")

        # Verify /explorer page is loaded
        expect(page.locator(self.USERNAME_LOCATOR)).to_be_visible(timeout=10000)
        current_url = page.url
        assert (
            "/explorer" in current_url
        ), f"Expected /explorer in url but got {current_url}"

    def click_on_download(self, page):
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
