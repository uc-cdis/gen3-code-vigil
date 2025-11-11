import time

import pytest
from playwright.sync_api import Page, expect
from utils import logger
from utils.test_execution import screenshot


class DicomPage(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url_portal}"
        # Endpoints
        if pytest.frontend_url:
            self.EXPLORER_ENDPOINT = f"{self.BASE_URL}/Explorer"
        else:
            self.EXPLORER_ENDPOINT = f"{self.BASE_URL}/explorer"
        # Locators
        self.IMAGING_STUDIES_TAB = "//h3[normalize-space()='Imaging Studies']"
        self.CORNERSTONE_CANVAS = "//*[@class='cornerstone-canvas']"

    def goto_explorer_page(self, page: Page, study_id):
        page.goto(self.EXPLORER_ENDPOINT)
        time.sleep(2)  # wait for page to load
        screenshot(page, "ExplorerPage")
        imaging_studies_tab = page.locator(self.IMAGING_STUDIES_TAB)
        expect(imaging_studies_tab).to_be_visible(timeout=5000)
        imaging_studies_tab.click()
        time.sleep(2)  # wait for page to load
        screenshot(page, "ImagingStudiesPage")
        STUDY_ID_HREF_XPATH = f"//a[contains(@href, 'StudyInstanceUIDs={study_id}')][1]"
        study_id_href = page.locator(STUDY_ID_HREF_XPATH)
        expect(study_id_href).to_be_visible(timeout=30000)
        href_url = study_id_href.get_attribute("href")
        page.goto(href_url)
        logger.info(f"Current URL: {page.url}")
        assert study_id in page.url, f"Expected {study_id} in {page.url}"
        cornerstone_canvas = page.locator(self.CORNERSTONE_CANVAS)
        time.sleep(2)  # wait for page to load
        screenshot(page, "OHIFViewerPage")
        expect(cornerstone_canvas).to_be_visible(timeout=30000)
