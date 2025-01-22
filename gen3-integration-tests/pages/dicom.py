import pytest
from playwright.sync_api import Page, expect
from utils import logger
from utils.test_execution import screenshot


class DicomPage(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url_portal}"
        # Endpoints
        self.EXPLORER_ENDPOINT = f"{self.BASE_URL}/explorer"
        # Locators
        self.IMAGING_STUDIES_TAB = "//h3[normalize-space()='Imaging Studies']"
        self.OHIF_TOOLS = "//*[@class='flex items-center justify-center space-x-2']"

    def goto_explorer_page(self, page: Page, study_id):
        page.goto(self.EXPLORER_ENDPOINT)
        screenshot(page, "ExplorerPage")
        imaging_studies_tab = page.locator(self.IMAGING_STUDIES_TAB)
        expect(imaging_studies_tab).to_be_visible(timeout=5000)
        imaging_studies_tab.click()
        screenshot(page, "ImagingStudiesPage")
        STUDY_ID_HREF_XPATH = f"//a[contains(@href, 'StudyInstanceUIDs={study_id}')][1]"
        study_id_href = page.locator(STUDY_ID_HREF_XPATH)
        expect(study_id_href).to_be_visible(timeout=5000)
        href_url = study_id_href.get_attribute("href")
        page.goto(href_url)
        logger.info(page.url)
        assert study_id in page.url, f"Expected {study_id} in {page.url}"
        ohif_tools = page.locator(self.OHIF_TOOLS)
        expect(ohif_tools).to_be_visible(timeout=5000)
        screenshot(page, "OHIFViewerPage")
