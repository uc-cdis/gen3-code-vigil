# Home page
import os

import pytest
from playwright.sync_api import Page
from utils import logger
from utils.test_execution import screenshot


class DiscoveryPage(object):
    def __init__(self):
        if pytest.frontend_url:
            self.BASE_URL = f"{pytest.root_url_portal}/Discovery"
        else:
            self.BASE_URL = f"{pytest.root_url_portal}/discovery"

        # LOCATORS
        self.READY_CUE = (
            '.discovery-search, [data-testid="discovery-textbox-search-bar"]'
        )
        self.NEXT_PAGE_BUTTON = "css=.ant-pagination-next:has-text('Next Page')"
        self.SEARCH_BAR = '//input[contains(@placeholder, "Search")]'
        self.OPEN_IN_WORKSPACE_BUTTON = (
            "css=button:has(span:is(:text('Open In Workspace')))"
        )

    def _tag_locator(self, tag_name: str) -> str:
        return f"css=span:is(:text('{tag_name}'))"

    def _study_locator(self, text: str) -> str:
        return f"(//*[contains(text(), '{text}') and not(self::input)])"

    def _study_selector_locator(self, study_id: str) -> str:
        return f"css=tr[data-row-key='{study_id}'] >> span >> input[type='checkbox']"

    def go_to(self, page: Page):
        page.goto(self.BASE_URL)
        screenshot(page, "DiscoveryPage")
        page.wait_for_selector(self.READY_CUE, state="visible", timeout=30000)

    def search_tag(self, page: Page, tag_name: str) -> None:
        page.click(self._tag_locator(tag_name))

    def search_text(self, page: Page, study_id: str) -> None:
        page.click(self.SEARCH_BAR)
        page.keyboard.type(study_id, delay=100)

    def study_found(self, page: Page, text: str) -> bool:
        study_row = page.locator(self._study_locator(text))
        try:
            study_row.wait_for()
            count = study_row.count()
            assert count == 1, f"Expected 1 count for {text}, but got {count}"
            return True
        except Exception:
            return False

    def open_in_workspace(self, page: Page, study_id: str) -> None:
        page.click(self._study_selector_locator(study_id))
        page.click(self.OPEN_IN_WORKSPACE_BUTTON)
