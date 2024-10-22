import os
import pytest

from utils import logger
from playwright.sync_api import Page, expect

from utils.test_execution import screenshot
from utils.gen3_admin_tasks import get_portal_config


class GWASPage(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url_portal}"
        # Endpoints
        self.ANALYSIS_ENDPOINT = f"{self.BASE_URL}/analysis"
        self.GWAS_UI_APP_ENDPOINT = f"{self.ANALYSIS_ENDPOINT}/GWASUIApp"
        # Locators
        self.ACCEPT_PRE_LOGIN_BUTTON = "//button[normalize-space()='Accept']"
        self.LOGIN_BUTTON = "//button[normalize-space()='InCommon Login']"
        self.PROJECT_SELECTOR_BOX = "//span[@role='button']//*[name()='svg']"
        self.PROJECT_SELECTOR_DROPDOWN = "//span[@class='ant-select-selection-item']"
        self.PROJECT_SUBMISSION = "//span[normalize-space()='Submit']"

    def login(
        self,
        page: Page,
        user,
    ):
        """
        Sets up Dev Cookie for main Account and logs in with Google
        Also checks if the access_token exists after login
        """
        expect(page.locator(self.LOGIN_BUTTON)).to_be_visible(timeout=10000)
        page.locator(self.ACCEPT_PRE_LOGIN_BUTTON).click()
        try:
            button = page.locator(self.LOGIN_BUTTON)
            if button.is_enabled(timeout=5000):
                button.click()
                logger.info(f"Clicked on login button : {self.LOGIN_BUTTON}")
        except Exception:
            logger.info(f"Login Button {self.LOGIN_BUTTON} not found or not enabled")
        screenshot(page, "AfterClickingLoginButton")
        expect(page.locator(f'//div[contains(text(), "{user}")]')).to_be_visible(
            timeout=10000
        )
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

    def goto_analysis_page(self, page: Page):
        page.goto(self.ANALYSIS_ENDPOINT)
        screenshot(page, "GWASAnalysisPage")

    def goto_gwas_ui_app_page(self, page: Page):
        page.goto(self.GWAS_UI_APP_ENDPOINT)
        screenshot(page, "GWASUIAppPage")

    def select_team_project(self, page: Page, project_name):
        logger.info("Clicking on Project selector box")
        project_selector_box = page.locator(self.PROJECT_SELECTOR_BOX)
        expect(project_selector_box).to_be_visible(timeout=5000)
        project_selector_box.click()

        logger.info("Clicking on Project selector dropdown")
        project_selector_dropdown = page.locator(self.PROJECT_SELECTOR_DROPDOWN)
        expect(project_selector_dropdown).to_be_visible(timeout=5000)
        project_selector_dropdown.click()

        logger.info("Clicking on the project")
        self.PROJECT_NAME = f"//div[@title='/gwas_projects/{project_name}']"
        project_name_locator = page.locator(self.PROJECT_NAME)
        expect(project_name_locator).to_be_visible(timeout=5000)
        project_name_locator.click()

        page.locator(self.PROJECT_SUBMISSION).click()

        screenshot(page, "AfterSelectingProject")
