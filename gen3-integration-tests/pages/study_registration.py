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
        self.STUDY_CHECKBOX = ""
        self.STUDY_DRAWER = "//div[@class='ant-drawer-body']"
        self.REQUEST_ACCESS_REGISTER = (
            "//button[@class='ant-btn ant-btn-text discovery-modal__request-button']"
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
        screenshot(page, "LoadedStudyTable")
        time.sleep(20)
        page.locator(self.SEARCH_BAR).fill(study_id)
        page.keyboard.press("Enter")
        time.sleep(10)
        screenshot(page, "SearchStudy")
        first_study = page.locator(self.STUDY_ROW)
        first_study.click()
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
        # adding sleep here,as form page takes sometime to load after you click on request access button.
        time.sleep(30)
        screenshot(page, "RequestAccessForm")
        access_form = page.locator(self.REQUEST_ACCESS_FORM_PAGE)
        access_form.wait_for(state="visible")
        project_title_field = page.locator(self.PROJECT_TITLE).input_value()
        assert (
            project_title_field == project_title
        ), f"Expect Project Title to be {project_title}, but got {project_title_field}"
        page.fill(self.FIRST_NAME, "Test")
        page.fill(self.LAST_NAME, "User")
        page.fill(self.EMAIL, email)
        page.fill(self.INSTITUTE, "University of Chicago")
        page.click(self.ROLE_RADIO_BUTTON)
        screenshot(page, "FilledRequestRegistrationForm")
        page.click(self.REQUEST_SUBMIT_BUTTON)
        time.sleep(10)
        screenshot(page, "SubmittedRequestAccessForm")

    def click_register_study(self, page: Page):
        register_button = page.locator(self.REGISTER_BUTTON)
        register_button.wait_for(state="visible")
        screenshot(page, "RegisterButton")
        register_button.click()

    def fill_registration_form(self, page: Page, uuid: str, study_name: str):
        current_url = page.url
        assert (
            current_url == self.BASE_URL
        ), f"Expected URL to be {self.BASE_URL}, but got {current_url}"
        page.wait_for_selector(self.REGISTER_STUDY_FORM_PAGE, state="visible")
        screenshot(page, "RegisterStudyForm")
        study_title = page.locator(self.STUDY_TITLE)
        expect(study_title).to_have_text(study_name)
        page.fill(self.CEDAR_UUID_FIELD, uuid)
        screenshot(page, "FilledRegistrationForm")
        page.click(self.REGISTER_SUBMIT_BUTTON)
        time.sleep(30)
        screenshot(page, "AfterRegisterSubmitClick")
