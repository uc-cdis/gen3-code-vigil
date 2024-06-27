import pytest
import os
from utils import logger
import time

from utils.test_execution import screenshot
from playwright.sync_api import Page, expect


class StudyRegistrationPage(object):
    def __init__(self):
        # Endpoints
        self.BASE_URL = f"{pytest.root_url_portal}/study-reg"
        self.REQUEST_ACCESS_PATH = f"{self.BASE_URL}/request-access"

        # Locators
        self.SEARCH_BAR = "//input[@placeholder='Search studies by keyword...']"
        self.STUDY_TABLE = "//div[@class='discovery-studies-container']"
        self.STUDY_ROW = "(//tr[@class='ant-table-row ant-table-row-level-0 discovery-table__row'])[1]"
        self.STUDY_CHECKBOX = "//td[@class='ant-table-cell ant-table-selection-column']//input[@type='checkbox']"
        # //td[@class='ant-table-cell ant-table-selection-column']//span[@class='ant-checkbox ant-checkbox-disabled']
        self.STUDY_DRAWER = "//div[@class='ant-drawer-body']"
        self.REQUEST_ACCESS_REGISTER = (
            "//span[normalize-space()='Request Access to Register This Study']"
        )
        self.REQUEST_ACCESS_FORM_PAGE = "//form[@id='generic-access-request-form']"
        self.PROJECT_TITLE = (
            "//textarea[@id='generic-access-request-form_Study Grant_doNotInclude']"
        )
        self.FIRST_NAME = "//input[@id='generic-access-request-form_First Name']"
        self.LAST_NAME = "//input[@id='generic-access-request-form_Last Name']"
        self.EMAIL = "//input[@id='generic-access-request-form_E-mail Address']"
        self.INSTITUTE = (
            "//input[@id='generic-access-request-form_Affiliated Institution']"
        )
        self.ROLE_RADIO_BUTTON = "//input[@value='Principal Investigator']"
        self.REQUEST_SUBMIT_BUTTON = "//button[@type='submit']"
        self.SUCCESS_MESSAGE = "//div[@class='ant-result ant-result-success']"
        self.REGISTER_BUTTON = "//span[normalize-space()='Register This Study']"
        self.REGISTER_STUDY_FORM_PAGE = "//form[@id='study-reg-form']"
        self.STUDY_TITLE = "//span[@class='ant-select-selection-item']"
        self.CEDAR_UUID_FIELD = (
            "//input[@placeholder='Provide your CEDAR user UUID here']"
        )
        self.REGISTER_SUBMIT_BUTTON = "//span[normalize-space()='Submit']"

    def search_study(self, page: Page, study_id: str):
        page.wait_for_selector(self.SEARCH_BAR)
        page.wait_for_selector(self.STUDY_TABLE)
        page.wait_for_selector(self.STUDY_ROW, timeout=60000)
        screenshot(page, "LoadedStudyTable")
        page.locator(self.SEARCH_BAR).fill(study_id)
        screenshot(page, "SearchStudy")
        checkbox = page.locator(self.STUDY_CHECKBOX)
        checkbox.click()
        screenshot(page, "ClickedCheckedBox")
        page.wait_for_selector(self.STUDY_DRAWER)
        screenshot(page, "StudyDrawer")

    def click_request_access_to_register(self, page: Page):
        register_request_access = page.locator(self.REQUEST_ACCESS_REGISTER)
        register_request_access.wait_for(state="visible")
        screenshot(page, "RegisterRequestAccessButton")
        register_request_access.click()

    def fill_request_access_form(self, page: Page, email: str, project_title: str):
        current_url = page.url
        assert (
            current_url == self.REQUEST_ACCESS_PATH
        ), f"Expected URL to be {self.REQUEST_ACCESS_PATH}, but got {current_url}"
        screenshot(page, "RegistrationForm")
        page.wait_for_selector(self.REQUEST_ACCESS_FORM_PAGE)
        page.wait_for_selector(
            self.PROJECT_TITLE, state=f"value={project_title}", timeout=10000
        )
        page.fill(self.FIRST_NAME, "Test")
        page.fill(self.LAST_NAME, "User")
        page.fill(self.EMAIL, email)
        page.fill(self.INSTITUTE, "University of Chicago")
        page.click(self.ROLE_RADIO_BUTTON)
        screenshot(page, "FilledRequestRegistrationForm")
        page.click(self.REQUEST_SUBMIT_BUTTON)

    def click_register_study(self, page: Page):
        register_button = page.locator(self.REGISTER_BUTTON)
        register_button.wait_for(state="visible")
        screenshot(page, "RegisterButton")
        register_button.click()

    def fill_registration_form(self, page: Page, uuid, study_name):
        current_url = page.url
        assert (
            current_url == self.BASE_URL
        ), f"Expected URL to be {self.BASE_URL}, but got {current_url}"
        page.wait_for_selector(self.REGISTER_STUDY_FORM_PAGE, state="visible")
        expect(self.STUDY_TITLE).to_have_attribute(study_name)
        page.fill(self.CEDAR_UUID_FIELD, uuid)
        screenshot(page, "FilledRegistrationForm")
        page.click(self.REGISTER_SUBMIT_BUTTON)
        time.sleep(30)
        screenshot(page, "AfterRegisterSubmitClick")
