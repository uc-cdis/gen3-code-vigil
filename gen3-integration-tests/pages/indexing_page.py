# Indexing Page
import os
import pytest

from utils import logger
from playwright.sync_api import expect, Page
from utils.test_execution import screenshot
from utils import TEST_DATA_PATH_OBJECT


class IndexingPage(object):
    def __init__(self):
        # Endpoints
        self.BASE_URL = f"{pytest.root_url_portal}/indexing"
        # Locators
        self.READY_CUE = "//div[@class='indexing-page']"  # Indexing page
        self.POP_UP_BOX = "//div[@class='popup__box']"
        # Locators - upload manifest
        self.UPLOAD_MANIFEST_FORM = (
            "//form[@class='index-flow-form']"  # MANIFEST_UPLOAD_FORM
        )
        self.FILE_UPLOAD = "//form[@class='index-flow-form']"
        self.FILE_INPUT = "//input[@type='file']"
        self.INDEX_FILE_BUTTON = "//button[contains(text(),'Index Files')]"
        self.DOWNLOAD_LOGS_BUTTON = "//button[contains(text(), 'Download Logs')]"
        self.FAILED_STATUS = (
            "//p[contains(text(),'The indexing job was dispatched, but failed to pro')]"
        )
        self.ERROR_IMAGE = "//*[name()='circle' and @id='Oval']"
        # Locators - download manifest
        self.DOWNLOAD_BUTTON = "//button[contains(text(),'Download')]"
        self.SUCCESS_MESSAGE = "//span[@class='index-files-green-label']"
        self.DOWNLOAD_MANIFEST_BUTTON = (
            "//button[contains(text(), 'Download Manifest')]"
        )

    def go_to(self, page: Page):
        page.goto(self.BASE_URL)
        page.wait_for_selector(self.READY_CUE, state="visible")
        screenshot(page, "IndexingPage")

    def upload_valid_indexing_manifest(self, page: Page, valid_manifest):
        form = page.locator(self.FILE_UPLOAD)
        expect(form).to_be_visible
        screenshot(page, "BeforeUploadManifest")
        page.set_input_files(self.FILE_INPUT, valid_manifest)
        screenshot(page, "AfterUploadManifest")
        index_files = page.locator(self.INDEX_FILE_BUTTON)
        index_files.click()
        screenshot(page, "AfterClickingIndexFileButton")
        page.wait_for_selector(self.POP_UP_BOX, state="visible")
        page.wait_for_selector(self.SUCCESS_MESSAGE, state="visible", timeout=240000)
        page.wait_for_selector(self.DOWNLOAD_LOGS_BUTTON, state="visible")
        page.wait_for_selector(self.DOWNLOAD_MANIFEST_BUTTON, state="visible")
        screenshot(page, "AfterUploadIsCompleted")

    def upload_invalid_indexing_manifest(self, page: Page, invalid_manifest):
        form = page.locator(self.FILE_UPLOAD)
        expect(form).to_be_visible
        screenshot(page, "BeforeUploadManifest")
        page.set_input_files(self.FILE_INPUT, invalid_manifest)
        screenshot(page, "AfterUploadManifest")
        index_files = page.locator(self.INDEX_FILE_BUTTON)
        index_files.click()
        screenshot(page, "AfterClickingIndexFileButton")
        page.wait_for_selector(self.POP_UP_BOX, state="visible")
        page.wait_for_selector(self.ERROR_IMAGE, state="visible", timeout=240000)
        failure_status = page.locator(self.FAILED_STATUS)
        screenshot(page, "AfterFailedStatus")
        expect(failure_status).to_be_visible

    def get_manifest_download_link(self, page: Page):
        download_button = page.locator(self.DOWNLOAD_BUTTON)
        expect(download_button).to_be_visible
        download_button.click()
        screenshot(page, "AfterDownloadManifestClick")
        page.wait_for_selector(self.POP_UP_BOX, state="visible")
        page.wait_for_selector(self.SUCCESS_MESSAGE, state="visible", timeout=120000)
        page.wait_for_selector(self.DOWNLOAD_MANIFEST_BUTTON, state="visible")
        download_manifest_button = page.locator(self.DOWNLOAD_MANIFEST_BUTTON)
        link = download_manifest_button.get_attribute("value")
        return link
