# Login Page
import os
import pytest

from cdislogging import get_logger
from playwright.sync_api import Page, expect

from utils.test_execution import screenshot

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class LoginPage(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url_portal}/login"
        # Locators
        self.READY_CUE = "//div[@class='nav-bar']"  # homepage navigation bar
        self.USERNAME_LOCATOR = "//div[@class='top-bar']//a[3]"  # username locator
        self.POP_UP_BOX = "//div[@id='popup']"  # pop_up_box
        self.RAS_LOGIN_BUTTON = "//button[@type='submit']"
        self.RAS_USERNAME_INPUT = "//input[@id='USER']"
        self.RAS_PASSWORD_INPUT = "//input[@id='PASSWORD']"
        self.RAS_GRANT_BUTTON = "//input[@value='Grant']"
        self.ORCID_REJECT_COOKIE_BUTTON = "//button[@id='onetrust-reject-all-handler']"
        self.ORCID_USERNAME_INPUT = "//input[@id='username']"
        self.ORCID_PASSWORD_INPUT = "//input[@id='password']"
        self.ORCID_LOGIN_BUTTON = "//button[@id='signin-button']"
        self.LOGIN_BUTTON = "//button[contains(text(), 'Dev login') or contains(text(), 'Google') or contains(text(), 'BioData Catalyst Developer Login')]"

    def go_to(self, page: Page):
        """Goes to the login page"""
        page.goto(self.BASE_URL)
        page.wait_for_selector(self.READY_CUE, state="visible")
        screenshot(page, "LoginPage")

    def login(self, page: Page, user="main_account", idp="Google"):
        """
        Sets up Dev Cookie for main Account and logs in with Google
        Also checks if the access_token exists after login
        """
        page.context.add_cookies(
            [{"name": "dev_login", "value": pytest.users[user], "url": self.BASE_URL}]
        )
        msg = r"ORCID Login" if idp == "ORCID" else r"Login from " + idp
        login_button = page.get_by_role(
            "button",
            name=re.compile(msg, re.IGNORECASE),
        )
        """
        // for manifest PRs
        name=re.compile(
                r"Dev login - set username in 'dev_login' cookie", re.IGNORECASE
            ),
        """
        expect(login_button).to_be_visible(timeout=5000)
        login_button.click()
        page.wait_for_timeout(3000)
        if idp == "ORCID":
            self.orcid_login(page)
        elif idp == "RAS":
            self.ras_login(page)

        page.screenshot(path="output/AfterLogin.png", full_page=True)
        page.wait_for_selector(self.USERNAME_LOCATOR, state="attached")
        self.handle_popup(page)
        screenshot(page, "AfterPopUpAccept")
        access_token_cookie = next(
            (
                cookie
                for cookie in page.context.cookies()
                if cookie["name"] == "access_token"
            ),
            None,
        )
        assert (
            access_token_cookie is not None
        ), "Access token cookie not found after login"

    def orcid_login(self, page: Page):
        # Handle the Cookie Settings Pop-Up
        if page.locator(self.ORCID_REJECT_COOKIE_BUTTON).is_visible():
            page.locator(self.ORCID_REJECT_COOKIE_BUTTON).click()
            page.wait_for_timeout(3000)
        # Perform ORCID Login
        orcid_login_button = page.locator(self.ORCID_LOGIN_BUTTON)
        expect(orcid_login_button).to_be_visible(timeout=5000)
        page.locator(self.ORCID_USERNAME_INPUT).fill(os.environ["CI_TEST_ORCID_ID"])
        page.locator(self.ORCID_PASSWORD_INPUT).fill(
            os.environ["CI_TEST_ORCID_PASSWORD"]
        )
        orcid_login_button.click()
        page.wait_for_timeout(3000)

    def ras_login(self, page: Page):
        # Perform RAS Login
        ras_login_button = page.locator(self.RAS_LOGIN_BUTTON)
        expect(ras_login_button).to_be_visible(timeout=5000)
        page.locator(self.RAS_USERNAME_INPUT).fill(os.environ["CI_TEST_RAS_ID"])
        page.locator(self.RAS_PASSWORD_INPUT).fill(os.environ["CI_TEST_RAS_PASSWORD"])
        ras_login_button.click()
        # Handle the Grant access button
        page.wait_for_timeout(3000)
        if page.locator(self.RAS_GRANT_BUTTON).is_visible():
            page.locator(self.RAS_GRANT_BUTTON).click()
        page.wait_for_timeout(3000)

    def logout(self, page: Page):
        """Logs out and wait for Login button on nav bar"""
        page.get_by_role("button", name="Logout").click()
        nav_bar_login_button = page.get_by_role("button", name="Login")
        screenshot(page, "AfterLogout")
        expect(nav_bar_login_button).to_be_visible

    # function to handle pop ups after login
    def handle_popup(self, page: Page):
        """Handling popups after login"""
        popup_message = page.query_selector(self.POP_UP_BOX)
        if popup_message:
            logger.info("Popup message found")
            page.evaluate(
                "(element) => {{element.scrollTop = element.scrollHeight;}}",
                popup_message,
            )
            screenshot(page, "DataUsePopup")
            accept_button = page.get_by_role("button", name="Accept")
            if accept_button:
                accept_button.click()
        else:
            logger.info("Popup message not found")
