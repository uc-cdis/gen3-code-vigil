# Exploration Page
import pytest
from pages.login import LoginPage
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect
from utils import logger
from utils.misc import retry
from utils.test_execution import screenshot


class ExplorationPage(object):
    def __init__(self):
        # Endpoints
        self.BASE_URL = f"{pytest.root_url_portal}"
        self.EXPLORATION_URL = f"{self.BASE_URL}/explorer"
        self.FILE_URL = f"{self.BASE_URL}/files"
        # Locators
        self.NAV_BAR = "//div[@class='nav-bar__nav--items']"
        self.GUPPY_TABS = "//div[@id='guppy-explorer-main-tabs']"
        self.FILE_TAB = "//h3[contains(text(), 'File')]"
        self.IMAGING_STUDIES_TAB = "//h3[contains(text(), 'Imaging Studies')]"
        self.GUPPY_FILTERS = "//div[@class='guppy-data-explorer__filter']"
        self.EXPORT_TO_PFB_BUTTON = "//button[contains(text(), 'Export to PFB')]"
        self.PFB_WAIT_FOOTER = "//div[text()='Your export is in progress.']"
        self.PFB_SUCCESS_FOOTER = (
            "//div[text()='Your cohort has been exported to PFB.']"
        )
        self.PFB_DOWNLOAD_LINK = (
            "//a[contains(text(), 'Click here to download your PFB')]"
        )
        self.CLOSE_BUTTON = "//button[contains(text(), 'Close')]"
        self.USERNAME_LOCATOR = "//div[@class='top-bar']//a[3]"
        self.LOGIN_TO_DOWNLOAD_BUTTON = (
            "//button[contains(text(), 'Login to download')]"
        )
        self.LOGIN_TO_DOWNLOAD_LIST_FIRST_ITEM = (
            '//*[contains(@class, " g3-dropdown__item ")][1]'
        )
        self.DOWNLOAD_BUTTON = '//button[contains(text(),"Download")][position()=1]'

    def navigate_to_exploration_tab_with_pfb_export_button(self, page: Page):
        page.wait_for_selector(self.NAV_BAR)
        screenshot(page, "NavigationBar")
        navbar_element = page.locator(self.NAV_BAR)
        exploration_link = (
            navbar_element.locator("a").filter(has_text="Exploration").first
        )
        files_link = navbar_element.locator("a").filter(has_text="Files").first
        if exploration_link:
            logger.info("Navigating to exploration page...")
            page.goto(self.EXPLORATION_URL)
            screenshot(page, "ExplorationPage")
            self.check_pfbExport_button(page)
        elif files_link:
            logger.info("Navigating to files page...")
            page.goto(self.FILE_URL)
            screenshot(page, "FilePage")
            self.check_pfbExport_button(page)
        else:
            logger.error(
                f"{self.BASE_URL} does not have Exploration or Files button in navigation bar. The test should not run in {self.BASE_URL}"
            )
            screenshot(page, "Navbar")

    def check_pfbExport_button(self, page: Page):
        page.wait_for_selector(self.GUPPY_TABS)
        page.wait_for_selector(self.GUPPY_FILTERS)
        page.wait_for_load_state("load")
        screenshot(page, "GuppyExplorationPage")
        try:
            export_to_pfb_button = page.locator(self.EXPORT_TO_PFB_BUTTON)
            expect(export_to_pfb_button).to_be_enabled(timeout=30000)
            print(
                "### The `Export to PFB` is enabled on the 'Data' tab. Just click on it!"
            )
            pfb_button = page.locator(self.EXPORT_TO_PFB_BUTTON)
            expect(pfb_button).to_be_enabled()
            pfb_button.click()
            screenshot(page, "ExportToPFBMessage")
        except TimeoutError:
            print(
                "### The `Export to PFB` is disabled on the 'Data' tab. Let's switch to the 'File' tab..."
            )
            page.locator(self.FILE_TAB).click()
            page.wait_for_selector(self.EXPORT_TO_PFB_BUTTON)
            screenshot(page, "FileTabsPage")
            pfb_button = page.locator(self.EXPORT_TO_PFB_BUTTON)
            screenshot(page, "ExportToPFBMessage")

    def check_pfb_status(self, page: Page):
        screenshot(page, "BeforePfbMessageFooter")
        try:
            logger.info("First Attempt to check PFB Message footer")
            wait_footer_locator = page.locator(self.PFB_WAIT_FOOTER)
            wait_footer_locator.wait_for(timeout=60000)
        except Exception:
            logger.info("Second Attempt to check PFB Message footer")
            self.navigate_to_exploration_tab_with_pfb_export_button(page)
            wait_footer_locator = page.locator(self.PFB_WAIT_FOOTER)
            wait_footer_locator.wait_for(timeout=60000)
        screenshot(page, "PfbWaitMessageFooter")
        success_footer_locator = page.locator(self.PFB_SUCCESS_FOOTER)
        success_footer_locator.wait_for(timeout=600000)
        screenshot(page, "PfbSuccessMessageFooter")
        pfb_link = page.locator(self.PFB_DOWNLOAD_LINK).get_attribute("href")
        return pfb_link

    def goto_explorer_page(self, page):
        # Goto explorer page
        page.goto(self.EXPLORATION_URL, wait_until="load")
        screenshot(page, "ExplorerPage")

        # Verify /explorer page is loaded
        expect(page.locator(self.USERNAME_LOCATOR)).to_be_visible(timeout=10000)
        current_url = page.url
        assert (
            "/explorer" in current_url
        ), f"Expected /explorer in url but got {current_url}"

    @retry(times=3, delay=30, exceptions=(AssertionError))
    def click_on_login_to_download(self, page):
        self.goto_explorer_page(page)
        # Click on the Download Button
        try:
            logger.info("Trying on First Tab")
            page.wait_for_load_state("load")
            download_button = page.locator(self.LOGIN_TO_DOWNLOAD_BUTTON).first
            screenshot(page, "FirstExplorationTab")
            download_button.click()
            logger.info("Found Login to Download button on First Tab")
        except (TimeoutError, PlaywrightTimeoutError):
            for tab in [self.FILE_TAB, self.IMAGING_STUDIES_TAB]:
                try:
                    logger.info(f"Trying on {tab} Tab")
                    page.locator(tab).click()
                    page.wait_for_load_state("load")
                    download_button = page.locator(self.LOGIN_TO_DOWNLOAD_BUTTON).first
                    screenshot(page, "ExplorationTab")
                    download_button.click()
                    logger.info(f"Found Login to Download button on {tab} Tab")
                    break
                except (TimeoutError, PlaywrightTimeoutError):
                    logger.info(f"Didn't Find Download button on {tab} Tab")
        screenshot(page, "AfterClickingLoginToDownload")
        login_to_download_list_first_item = page.locator(
            self.LOGIN_TO_DOWNLOAD_LIST_FIRST_ITEM
        )
        if login_to_download_list_first_item.count() > 0:
            expect(login_to_download_list_first_item).to_be_enabled()
            login_to_download_list_first_item.click()

    @retry(times=3, delay=30, exceptions=(AssertionError))
    def click_on_download(self, page):
        self.goto_explorer_page(page)
        login_page = LoginPage()
        screenshot(page, "BeforeClickingOnDownload")
        login_page.handle_popup(page)
        # Click on the Download Button
        try:
            logger.info("Trying on First Tab")
            download_button = page.locator(self.DOWNLOAD_BUTTON).first
            screenshot(page, "FirstExplorationTab")
            download_button.click()
            logger.info("Found Download button on First Tab")
        except (TimeoutError, PlaywrightTimeoutError):
            for tab in [self.FILE_TAB, self.IMAGING_STUDIES_TAB]:
                try:
                    logger.info(f"Trying on {tab} Tab")
                    page.locator(tab).click()
                    page.wait_for_load_state("load")
                    download_button = page.locator(self.DOWNLOAD_BUTTON).first
                    screenshot(page, "ExplorationTab")
                    download_button.click()
                    logger.info(f"Found Download button on {tab} Tab")
                    break
                except (TimeoutError, PlaywrightTimeoutError):
                    logger.info(f"Didn't Find Download button on {tab} Tab")
        screenshot(page, "AfterClickingDownload")
        login_to_download_list_first_item = page.locator(
            self.LOGIN_TO_DOWNLOAD_LIST_FIRST_ITEM
        )
        if login_to_download_list_first_item.count() > 0:
            expect(login_to_download_list_first_item).to_be_enabled()
            login_to_download_list_first_item.click()
