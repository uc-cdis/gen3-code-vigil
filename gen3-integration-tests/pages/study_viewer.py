import pytest
import os
from utils import logger
import utils.gen3_admin_tasks as gat

from utils.test_execution import screenshot
from playwright.sync_api import Page, expect

get_index = gat.get_study_viewer_index(pytest.namespace)
indexFile = get_index["study_viewer_index.txt"].splitlines()
if len(indexFile) < 1:
    raise Exception("Index File does not contain expected data format (1 lines)")
study_viewer_index = indexFile[0]


class StudyViewerPage(object):
    def __init__(self):
        # Endpoints
        self.BASE_URL = f"{pytest.root_url_portal}/study-viewer"
        self.STUDY_VIEWER_URL = f"{self.BASE_URL}/{study_viewer_index}"

        # Locators
        self.READY_CUE = "//div[@class='study-viewer']"
        self.LOGINRA_BUTTON = "//button[contains(text(), 'Login to Request Access')]"
        self.SHOW_DETAILS = ".ant-collapse-header-text"
        self.REQUEST_ACCESS_BUTTON = "//button[contains(text(),'Request Access')]"
        self.DOWNLOAD_BUTTON = "//button[contains(text(),'Download')]"

    def go_to(self, page: Page):
        page.goto(self.STUDY_VIEWER_URL)
        page.wait_for_selector(self.READY_CUE, state="visible")
        screenshot(page, "StudyViewerPage")

    def click_show_details(self, page: Page):
        learn_more = page.locator(self.SHOW_DETAILS).first
        learn_more.wait_for(state="visible", timeout=30000)
        learn_more.click()
        screenshot(page, "ShowDetails")

    def click_login_request_access_button(self, page: Page):
        login_request_access = page.locator(self.LOGINRA_BUTTON)
        login_request_access.wait_for(state="visible")
        login_request_access.click()
        page.wait_for_url(f"{pytest.root_url_portal}/login")
        assert (
            "/login" in page.url
        ), f"Expected to be on /login page, but current URL is {page.url}"

    def click_request_access_button(self, page: Page):
        request_access = page.locator(self.REQUEST_ACCESS_BUTTON)
        request_access.wait_for()
        request_access.click()
        screenshot(page, "ClickRequestAccessButton")
