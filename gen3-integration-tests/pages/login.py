# Login Page
import os
import pytest
import time

from utils import logger
from playwright.sync_api import Page, expect

from utils.test_execution import screenshot
from utils.gen3_admin_tasks import get_portal_config


class LoginPage(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url_portal}/login"
        # Locators
        self.READY_CUE = "//div[@class='nav-bar']"  # homepage navigation bar
        self.USERNAME_LOCATOR = "//div[@class='top-bar']//a[3]"  # username locator
        self.POP_UP_BOX = "//div[@class='popup__box']"  # pop_up_box
        self.POP_UP_ACCEPT_BUTTON = "//button[contains(text(),'Accept')]"
        self.RAS_LOGIN_BUTTON = "//button[contains(text(),'Login with RAS')]"
        self.RAS_SIGN_IN_BUTTON = "//button[contains(text(),'Sign in')]"
        self.RAS_USERNAME_INPUT = "//input[@id='USER']"
        self.RAS_PASSWORD_INPUT = "//input[@id='PASSWORD']"
        self.RAS_GRANT_BUTTON = "//input[@value='Grant']"
        self.RAS_AUTHORIZATION_BOX = "//div[@class='auth-list']"
        self.RAS_ACCEPT_AUTHORIZATION_BUTTON = "//button[contains(text(), 'authorize')]"
        self.RAS_DENY_AUTHORIZATION_BUTTON = "//button[contains(text(), 'Cancel')]"
        self.ORCID_REJECT_COOKIE_BUTTON = "//button[@id='onetrust-reject-all-handler']"
        self.ORCID_USERNAME_INPUT = "//input[@id='username-input']"
        self.ORCID_PASSWORD_INPUT = "//input[@id='password']"
        self.ORCID_LOGIN_BUTTON = "//button[@id='signin-button']"
        self.LOGIN_BUTTON_LIST = "//div[@class='login-page__central-content']"
        # from the list below, the LOGIN_BUTTON is selected in order of preference
        # if it doesnt find DEV_LOGIN button, it looks for GOOGLE LOGIN button instead and so on
        self.LOGIN_BUTTONS = [
            "//button[contains(text(), 'Dev login')]",
            "//button[contains(text(), 'Google')]",
            "//button[contains(text(), 'BioData Catalyst Developer Login')]",
        ]
        self.USER_PROFILE_DROPDOWN = (
            "//i[@class='g3-icon g3-icon--user-circle top-icon-button__icon']"
        )
        self.LOGOUT_NORMALIZE_SPACE = "//a[normalize-space()='Logout']"

    def go_to(self, page: Page, url=None):
        """Goes to the login page"""
        if url:
            page.goto(url)
        else:
            page.goto(self.BASE_URL)
            page.wait_for_selector(self.READY_CUE, state="visible")
        screenshot(page, "LoginPage")

    def login(
        self,
        page: Page,
        user="main_account",
        idp="Google",
        validate_username_locator=True,
    ):
        """
        Sets up Dev Cookie for main Account and logs in with Google
        Also checks if the access_token exists after login
        """
        page.context.add_cookies(
            [
                {
                    "name": "dev_login",
                    "value": pytest.users[user],
                    "url": pytest.root_url_portal,
                }
            ]
        )
        # printing cookies if needed for debugging purposes
        cookies = page.context.cookies()
        res = get_portal_config(pytest.namespace)
        expect(page.locator(self.LOGIN_BUTTON_LIST)).to_be_visible(timeout=10000)
        if idp == "ORCID":
            self.orcid_login(page)
            logged_in_user = os.environ["CI_TEST_ORCID_USERID"]
        elif idp == "RAS":
            self.ras_login(page)
            logged_in_user = os.environ["CI_TEST_RAS_USERID"]
        else:
            logger.info(self.LOGIN_BUTTONS)
            for login_button in self.LOGIN_BUTTONS:
                logger.info(login_button)
                try:
                    button = page.locator(login_button)
                    if button.is_enabled(timeout=5000):
                        button.click()
                        logger.info(f"Clicked on login button : {login_button}")
                        break
                except Exception:
                    logger.info(f"Login Button {login_button} not found or not enabled")
                logged_in_user = pytest.users[user]
        # Check if useProfileDropdown is set to True and click on the Profile Dropdown
        if res.get("components", {}).get("topBar", {}).get("useProfileDropdown", ""):
            page.locator(self.USER_PROFILE_DROPDOWN).click()
        if validate_username_locator:
            res = get_portal_config()
            # Check if useProfileDropdown is set to True and click on dropdown for username to be visible
            if (
                res.get("components", {})
                .get("topBar", {})
                .get("useProfileDropdown", "")
            ):
                page.locator(self.USER_PROFILE_DROPDOWN).click()
            expect(
                page.locator(f'//div[contains(text(), "{logged_in_user}")]')
            ).to_be_visible(timeout=10000)
        screenshot(page, "AfterLogin")
        self.handle_popup(page)
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
        return access_token_cookie

    def orcid_login(self, page: Page):
        # Click on 'ORCID Login' on Gen3 Login Page
        page.locator("//button[normalize-space()='ORCID Login']").click()
        # Perform ORCID Login
        orcid_login_button = page.locator(self.ORCID_LOGIN_BUTTON)
        expect(orcid_login_button).to_be_visible(timeout=5000)
        page.locator(self.ORCID_USERNAME_INPUT).fill(os.environ["CI_TEST_ORCID_USERID"])
        page.locator(self.ORCID_PASSWORD_INPUT).fill(
            os.environ["CI_TEST_ORCID_PASSWORD"]
        )
        # Handle the Cookie Settings Pop-Up
        if page.locator(self.ORCID_REJECT_COOKIE_BUTTON).is_visible():
            page.locator(self.ORCID_REJECT_COOKIE_BUTTON).click()
        screenshot(page, "BeforeORCIDLogin")
        orcid_login_button.click()

    def ras_login(
        self,
        page: Page,
        username="",
        password="",
        portal_test=True,
    ):
        username = username or os.environ["CI_TEST_RAS_USERID"]
        password = password or os.environ["CI_TEST_RAS_PASSWORD"]
        if portal_test is True:
            # Click on 'Login from RAS' on Gen3 Login Page
            page.locator("//button[normalize-space()='Login from RAS']").click()
            # Perform RAS Login
            self.ras_login_form(page, username, password)
            screenshot(page, "RASAfterClickingGrantButton")
        else:
            self.ras_login_form(page, username, password)
            if page.locator(self.RAS_ACCEPT_AUTHORIZATION_BUTTON).is_visible(
                timeout=5000
            ):
                logger.info("Clicking on Authorization button")
                page.locator(self.RAS_ACCEPT_AUTHORIZATION_BUTTON).click()
                time.sleep(5)
                screenshot(page, "RASAfterClickingAuthorizationButton")

    def ras_login_form(self, page: Page, username: str, password: str):
        screenshot(page, "RASLoginPage")
        page.locator(self.RAS_USERNAME_INPUT).fill(username)
        page.locator(self.RAS_PASSWORD_INPUT).fill(password)
        ras_signin_button = page.locator(self.RAS_SIGN_IN_BUTTON)
        ras_signin_button.click()
        screenshot(page, "RASAfterLogging")
        # Handle the Grant access button
        if page.locator(self.RAS_GRANT_BUTTON).is_visible(timeout=5000):
            logger.info("Clicking on Grant button")
            page.locator(self.RAS_GRANT_BUTTON).click()

    def logout(self, page: Page):
        """Logs out and wait for Login button on nav bar"""
        res = get_portal_config()
        # Check if useProfileDropdown is set to True and perform logout accordingly
        if res.get("components", {}).get("topBar", {}).get("useProfileDropdown", ""):
            page.locator(self.USER_PROFILE_DROPDOWN).click()
            page.locator(self.LOGOUT_NORMALIZE_SPACE).click()
        # Click on Logout button to logout
        else:
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
            accept_button = page.locator(self.POP_UP_ACCEPT_BUTTON)
            if accept_button:
                accept_button.click()
            screenshot(page, "AfterPopUpAccept")
        else:
            logger.info("Popup message not found")
