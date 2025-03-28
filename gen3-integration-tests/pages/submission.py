# Submission page
import os
import time

import pytest
from cdislogging import get_logger
from playwright.sync_api import Page, expect
from utils.misc import retry
from utils.test_execution import screenshot

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


# Not in Use
class SubmissionPage(object):
    def __init__(self):
        # Endpoints
        self.BASE_URL = f"{pytest.root_url_portal}/submission"
        self.FILES_URL = f"{self.BASE_URL}/files"

        # Locators
        self.PROJECT_LIST_TABLE = (
            "//div[@class='project-table']//div[@class='base-table']"
        )
        self.MAP_BUTTON = "//button[@class='submission-header__section-button g3-button g3-button--primary']"
        self.FILES_TABLE = "//div[@class='map-files']"
        self.FILES_CHECKBOX = "//input[type='checkbox'][@id='{guid}']"
        self.START_MAP_BUTTON = (
            "//button[@class='g3-icon g3-icon--lg g3-button g3-button--primary']"
        )
        self.MAP_FORM = "//div[@class='map-data-model__form']"
        self.PROJECT_SELECT_INPUT = "//input[@id='react-select-2-input']"
        self.FILE_NODE_SELECT_INPUT = "//input[@id='react-select-3-input']"
        self.REQUIRED_FIELDS = "//div[@class='map-data-model__detail-section']"
        self.MAPPING_SUBMIT_BUTTON = "//button[contains(text(),'Submit')]"
        self.FILE_READY = "//p[text()='1 files mapped successfully!']"
        self.SUBMISSION_HEADER_CLASS = "//div[@class='submission-header']"
        self.UNMAPPED_FILE_ROW_CLASS = ".map-files__table-row"
        self.BACK_TO_DATA_SUBMISSION = (
            "//div[normalize-space()='Back to Data Submission']"
        )
        self.NO_FILES_MSG = "No files have been uploaded."
        self.MAPPED_FILES_COUNT_AND_SIZE = (
            "//div[text()='Map My Files']/following-sibling::div[@class='h4-typo']"
        )
        self.SUBMISSION_PAGE_SELECT_FIRST_ITEM = '//*[contains(@class, "map-data-model__node-form-section")]//*[contains(@class, "Select-menu-outer") or contains(@class, "react-select__menu")]//*[contains(@class, "Select-option") or contains(@class, "react-select__option")][1]'
        self.SUBMISSION_PAGE_PROJECT = "//div[@class='h4-typo'][normalize-space()='Project']/following-sibling::div[@class='input-with-icon']"
        self.SUBMISSION_PAGE_FILE_NODE = "//div[@class='h4-typo'][normalize-space()='File Node']/following-sibling::div[@class='input-with-icon']"
        self.SUBMISSION_PAGE_CORE_METEDATA_COLLECTION = "//div[@class='h4-typo'][normalize-space()='core_metadata_collection']/following::div[@class='input-with-icon']"
        self.SUBMISSION_PAGE_FIELDS = (
            "//div[@class='h4-typo']/following::div[@class='input-with-icon']"
        )
        self.SUBMISSION_PAGE_SUBMIT_BUTTON = "//button[@type='button']"

    def go_to_submission_page(self, page: Page):
        """Goes to the submission page"""
        page.goto(self.BASE_URL)
        page.wait_for_selector(self.MAP_BUTTON, state="visible")
        page.wait_for_selector(self.PROJECT_LIST_TABLE, state="visible")
        screenshot(page, "SubmissionPage")

    def go_to_files_page(self, page: Page):
        """Goes to the files page"""
        page.goto(self.FILES_URL)
        page.wait_for_selector(self.FILES_TABLE, state="visible")
        screenshot(page, "FilesPage")

    def construct_checkbox_with_guid(self, guid: str):
        """Constructs checkbox with guid provided in the test"""
        checkbox_selector = self.FILES_CHECKBOX.format(guid=guid)
        return checkbox_selector

    def checkbox_if_clickable(self, page: Page, selector: str):
        """Wait for a checkbox with provided guid is clickable"""
        try:
            page.wait_for_selector(selector, timeout=30000, state="attached")
            screenshot(page, "ClickCheckboxUnmappedFiles")
            return True
        except TimeoutError:
            return False

    def fill_mapping_form(self, page: Page, target_node: str):
        """Fill the mapping form with project and file node"""
        page.wait_for_selector(self.MAP_FORM)
        page.locator(self.PROJECT_SELECT_INPUT).fill("DEV-TEST")
        page.keyboard.press("Enter")
        page.locator(self.FILE_NODE_SELECT_INPUT).fill(f"{target_node}")
        page.keyboard.press("Enter")
        screenshot(page, "")
        page.wait_for_selector(self.REQUIRED_FIELDS)
        # looping through the required field
        start = 4
        end = 8
        for i in range(start, end):
            field = f"//input[@id='react-select-{i}-input']"
            try:
                page.click(field)
                page.keyboard.press("Enter")
            except Exception as e:
                logger.info(f"Error encountered while filling the form : {e}")
        page.wait_for_selector(self.MAPPING_SUBMIT_BUTTON)
        page.click(self.MAPPING_SUBMIT_BUTTON)

    @retry(times=3, delay=10, exceptions=(AssertionError))
    def check_unmapped_files_submission_page(self, page: Page, text):
        self.go_to_submission_page(page=page)
        page.wait_for_selector(self.SUBMISSION_HEADER_CLASS, state="visible")
        screenshot(page, "CheckUnmappedFiles")
        text_from_page = page.locator(self.MAPPED_FILES_COUNT_AND_SIZE).text_content()
        assert text_from_page == text, f"Expected {text}, but got {text_from_page}"

    def map_files(self, page: Page):
        self.go_to_files_page(page=page)
        # Select all files
        map_files_button = page.locator("//button[normalize-space()='Map Files']")
        expect(map_files_button).to_be_visible(timeout=5000)
        page.locator("//input[@id='0']").click()
        page.locator("//button[normalize-space()='Map Files (1)']").click()
        screenshot(page, "MappingFile")

    def select_submission_fields(self, page):
        screenshot(page, "BeforeFillingInFields")
        # Project Selection
        page.locator(self.SUBMISSION_PAGE_PROJECT).click()
        page.click("text='DEV-test'")

        # File Node Selection
        page.locator(self.SUBMISSION_PAGE_FILE_NODE).click()
        page.click(self.SUBMISSION_PAGE_SELECT_FIRST_ITEM)

        elements = page.locator(self.SUBMISSION_PAGE_FIELDS)
        # Loop through each element and perform a click operation
        for i in range(2, elements.count()):
            elements.nth(i).click()
            dropdown_menu = page.locator(".react-select__menu")
            is_dropdown_present = dropdown_menu.is_visible()
            if not is_dropdown_present:
                screenshot(page, f"BeforeSelectField-{i}")
                # Set the field value to "abc" if there is no dropdown box
                input_locator = elements.nth(i).locator("//input")
                input_locator.fill("abc")
            else:
                # Click on the first item in the dropdown box
                page.click(self.SUBMISSION_PAGE_SELECT_FIRST_ITEM)

        # core_metadata_collection Selection
        page.click(self.SUBMISSION_PAGE_CORE_METEDATA_COLLECTION)
        page.click(self.SUBMISSION_PAGE_SELECT_FIRST_ITEM)

        screenshot(page, "BeforeSubmitMappingFile")

        # Click on Submit field
        page.locator(self.SUBMISSION_PAGE_SUBMIT_BUTTON).click()
