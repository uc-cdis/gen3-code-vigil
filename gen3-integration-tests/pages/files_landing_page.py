import os
import pytest

from cdislogging import get_logger
from playwright.sync_api import Page

from utils.test_execution import screenshot

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class FilesLandingPage(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url_portal}/files"
        self.METADATA_PAGE_CLASS = "//div[@class='core-metadata-page']"
        self.METADATA_PAGE_PICTURE_CLASS = "//div[@class='core-metadata-page__picture']"
        self.METADATA_PAGE_HEADER_CLASS = "//div[@class='core-metadata-page__header']"
        self.METADATA_PAGE_TABLE_CLASS = "//div[@class='core-metadata-page__table']"
        self.BACK_LINK_CLASS = "//div[normalize-space()='Back to File Explorer']"
        self.TABLE_TITLE_TEXT = "//th[normalize-space()='More Data Info']"
        self.DOWNLOAD_BUTTON_XPATH = '//button[contains(@class, "button-primary-orange") and contains(text(), "Download")]'

    def goto_metadata_page(self, page: Page, guid):
        """Goto Metadata Page with Guid"""
        page.goto(f"{self.BASE_URL}/{guid}")
        page.wait_for_selector(self.METADATA_PAGE_CLASS, state="visible")
        screenshot(page, "MetadataLandingPage")

    def verify_metadata_page_elements(self, page: Page):
        """Verify the elements on the page are visible"""
        if not page.locator(self.METADATA_PAGE_CLASS).is_visible():
            logger.error("core-metadata-page element is missing")
            raise
        if not page.locator(self.METADATA_PAGE_PICTURE_CLASS).is_visible():
            logger.error("core-metadata-page__picture element is missing")
            raise
        if not page.locator(self.METADATA_PAGE_HEADER_CLASS).is_visible():
            logger.error("ore-metadata-page__header element is missing")
            raise
        if not page.locator(self.METADATA_PAGE_TABLE_CLASS).is_visible():
            logger.error("core-metadata-page__table element is missing")
            raise
        if not page.locator(self.BACK_LINK_CLASS).is_visible():
            logger.error("back-link element is missing")
            raise
        if not page.locator(self.TABLE_TITLE_TEXT).is_visible():
            logger.error("More Data Info element is missing")
            raise
        if not page.locator(self.DOWNLOAD_BUTTON_XPATH).is_visible():
            logger.error("Download element is missing")
            raise
