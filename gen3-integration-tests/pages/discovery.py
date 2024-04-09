# Home page
import os
import pytest

from cdislogging import get_logger
from playwright.sync_api import Page

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class DiscoveryPage(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url_portal}/discovery"

        # LOCATORS
        self.READY_CUE = "css=.discovery-search"
        self.NEXT_PAGE_BUTTON = "css=.ant-pagination-next:has-text('Next Page')"
        self.SEARCH_BAR = (
            "css=div.discovery-search-container >> span >> input[type='text']"
        )
        self.OPEN_IN_WORKSPACE_BUTTON = (
            "css=button:has(span:is(:text('Open In Workspace')))"
        )

    def _tag_locator(self, tag_name: str) -> str:
        return f"css=span:is(:text('{tag_name}'))"

    def _study_locator(self, study_id: str) -> str:
        return f"css=tr[data-row-key='{study_id}']"

    def _study_selector_locator(self, study_id: str) -> str:
        return f"css=tr[data-row-key='{study_id}'] >> span >> input[type='checkbox']"

    def go_to(self, page: Page):
        page.goto(self.BASE_URL)
        page.wait_for_selector(self.READY_CUE, state="visible")

    def search_tag(self, page: Page, tag_name: str) -> None:
        page.click(self._tag_locator(tag_name))

    def search_text(self, page: Page, text: str) -> None:
        page.click(self.SEARCH_BAR)
        page.keyboard.type(text)

    def study_found(self, page: Page, study_id: str) -> bool:
        study_row = page.locator(self._study_locator(study_id))
        try:
            study_row.wait_for()
            return True
        except Exception:
            return False

    def open_in_workspace(self, page: Page, study_id: str) -> None:
        page.click(self._study_selector_locator(study_id))
        page.click(self.OPEN_IN_WORKSPACE_BUTTON)
