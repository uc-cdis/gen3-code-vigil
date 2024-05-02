# Exploration Page
import os
import pytest
import time

from cdislogging import get_logger
from playwright.sync_api import Page, expect
from utils.test_execution import screenshot

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class ExplorationPage(object):
    def __init__(self):
        # Endpoints
        self.BASE_URL = f"{pytest.root_url_portal}"
        self.EXPLORATION_URL = f"{self.BASE_URL}/explorer"
        self.FILE_URL = f"{self.BASE_URL}/files"
        # Locators
        self.NAV_BAR = "//nav[@class='nav-bar__nav--items']"
        self.GUPPY_TABS = "//div[@id='guppy-explorer-main-tabs']"
        self.FILE_TAB = "//h3[contains(text(), 'File')]"
        self.GUPPY_FILTERS = "//div[@class='guppy-data-explorer__filter']"
        self.EXPORT_TO_PFB_BUTTON = "//button[contains(text(), 'Export to PFB')]"
        self.PFB_WAIT_FOOTER = "//div[@class='explorer-button-group__toaster-text']//div[contains(.,'Please do not navigate away from this page until your export is finished.')]"
        self.PFB_ERROR_FOOTER = "//div[@class='explorer-button-group__toaster-text']//div[contains(.,'There was an error exporting your cohort.')]"
        # self.PFB_SUCCESS_FOOTER = "//div[@class='explorer-button-group__toaster-text']//a[contains(.,\'Click here to download your PFB.\')]"
        self.PFB_SUCCESS_FOOTER = (
            "//a[contains(@class, 'explorer-button-group__toaster-dl-link')]"
        )
        self.CLOSE_BUTTON = "//button[contains(text(), 'Close')]"

    def go_to_and_check_button(self, page: Page):
        page.wait_for_selector(self.NAV_BAR)
        screenshot(page, "navigationBar")
        navbar_element = page.locator(self.NAV_BAR)
        exploration_link = (
            navbar_element.locator("a").filter(has_text="Exploration").first
        )
        files_link = navbar_element.locator("a").filter(has_text="Files").first
        if exploration_link:
            logger.info("Navigating to exploration page...")
            page.goto(self.EXPLORATION_URL)
            screenshot(page, "explorationPage")
            self.check_pfbExport_button(page)
        elif files_link:
            logger.info("Navigating to files page...")
            page.goto(self.FILE_URL)
            screenshot(page, "filePage")
            self.check_pfbExport_button(page)
        else:
            logger.error(
                f"{self.BASE_URL} does not have Exploration or Files button in navigation bar. The test should not run in {self.BASE_URL}"
            )
            screenshot(page, "navbar")

    def check_pfbExport_button(self, page: Page):
        page.wait_for_selector(self.GUPPY_TABS)
        page.wait_for_selector(self.GUPPY_FILTERS)
        screenshot(page, "guppyExplorationPage")
        try:
            export_to_pfb_button = page.locator(self.EXPORT_TO_PFB_BUTTON)
            export_to_pfb_button.wait_for()
        except TimeoutError:
            print(
                "### The `Export to PFB` is disabled on the 'Data' tab. Let's switch to the 'File' tab..."
            )
            page.locator(self.FILE_TAB).click()
            page.wait_for_selector(self.EXPORT_TO_PFB_BUTTON)
            screenshot(page, "fileTabsPage")
        else:
            print(
                "### The `Export to PFB` is enabled on the 'Data' tab. Just click on it!"
            )
            page.wait_for_selector("//button[contains(text(), 'Export to PFB')]")

    def check_pfb_status(self, page: Page):
        pfb_button = page.locator(self.EXPORT_TO_PFB_BUTTON)
        pfb_button.click()
        screenshot(page, "exportToPFBMessage")
        success_footer_locator = page.locator(self.PFB_SUCCESS_FOOTER)
        success_footer_locator.wait_for(timeout=300000)
        screenshot(page, "pfbSuccessMessageFooter")
        pfb_link = success_footer_locator.get_attribute("href")
        return pfb_link
