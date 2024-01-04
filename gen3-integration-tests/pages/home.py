# Home page
import os
import pytest

from cdislogging import get_logger
from playwright.sync_api import Page

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class HomePage(object):
    def __init__(self):
        self.BASE_URL = pytest.root_url

    def go_to(self, page: Page):
        page.goto(self.BASE_URL)

    def landing_page(self):
        if "heal" in pytest.tested_env.lower():
            return f"{self.BASE_URL}/landing"
        elif "ibd" in pytest.tested_env.lower():
            return f"{self.BASE_URL}/"
        else:
            return f"{self.BASE_URL}/login"
