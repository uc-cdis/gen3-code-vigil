# Data Library Page

import re

import pytest
from playwright.sync_api import Page, TimeoutError
from utils.test_execution import screenshot


class DataLibraryPage(object):
    def __init__(self):
        if pytest.navigation_urls.get("Data Library"):
            self.BASE_URL = {pytest.root_url_portal} + pytest.navigation_urls[
                "Data Library"
            ]
        else:
            self.BASE_URL = f"{pytest.root_url_portal}/DataLibrary"

        # LOCATORS
        self.READY_CUE = "button:has-text('Data Library')"

        self.FILE_CHECKBOX = "input[type='checkbox']"

        self.EXPORT_DROPDOWN = "input.mantine-Select-input"

        self.EXPORT_BUTTON = "css=button:has-text('Export')"

        self.CLOSE_MODAL_BUTTON = "internal:role=button[name='Close Modal'i]"

        self.DELETE_LIST_BUTTON = "internal:role=button[name='delete list'i]"

    def go_to(self, page: Page):
        page.goto(self.BASE_URL)
        screenshot(page, "DataLibraryPage")

        try:
            page.wait_for_selector(
                self.READY_CUE,
                state="visible",
                timeout=30000,
            )
        except TimeoutError:
            raise AssertionError("Data Library page did not load within 30 seconds")

    def assert_first_row_exists(self, page: Page):
        """Asserts that the first expandable row exists and is visible."""
        first_row_btn = (
            page.get_by_role("button").filter(has_text=re.compile(r"^$")).nth(1)
        )
        # wait for the locator to become visible
        first_row_btn.wait_for(state="visible", timeout=150000)
        assert (
            first_row_btn.is_visible()
        ), "Error: The first row was not visible on the Data Library page."

    def expand_first_row(self, page: Page):
        page.get_by_role("button").filter(has_text=re.compile(r"^$")).nth(1).click()

    def select_first_child_entry(self, page: Page):
        page.locator(self.FILE_CHECKBOX).nth(1).check()

    def retrieve_selected_data(self, page: Page):
        page.get_by_role("button", name="Retrieve Selected Data").click()

    def select_all_entries(self, page: Page):
        checkbox = page.get_by_role("checkbox", name="Toggle select all")
        checkbox.check()

    def select_export_to_terra(self, page: Page):
        page.locator(".animate-spin").wait_for(state="detached")
        dropdown = page.locator(self.EXPORT_DROPDOWN).first
        dropdown.wait_for(state="visible")
        dropdown.click()
        page.get_by_role("option", name="Export: Terra").click()

    def export_data(self, page: Page):
        page.click(self.EXPORT_BUTTON)

    def close_modal(self, page: Page):
        page.click(self.CLOSE_MODAL_BUTTON)

    def delete_list(self, page: Page):
        page.click(self.DELETE_LIST_BUTTON)
