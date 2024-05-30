# Gen3 Frontend Framework Landing Page
import os
import pytest
import re

from utils import logger
from playwright.sync_api import Page, expect

from utils.test_execution import screenshot


class Gen3FFLandingPage(object):
    def __init__(self):
        # PATHS
        self.BASE_URL = f"{pytest.root_url}/landing"

        # LOCATORS
        self.READY_CUE = "css=.flex-grow"

    def go_to(self, page: Page):
        page.goto(self.BASE_URL)
        page.wait_for_selector(self.READY_CUE, state="visible")
        screenshot(page, "GEN3FF_LANDING")

    def is_current_page(self, page: Page):
        expect(page).to_have_url(self.BASE_URL)

    def check_button(self, page: Page, button: str, expected_url: str):
        page.click(f"css=a:has-text('{button}')")
        screenshot(page, f"GEN3FF_LANDING_BUTTON_{button.upper()}")
        expect(page).to_have_url(re.compile(f".*{expected_url}"))
