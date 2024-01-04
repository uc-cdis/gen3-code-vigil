# Home page
import os
import pytest

from cdislogging import get_logger
from playwright.sync_api import Page

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class LoginPage(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/login"

    def go_to(self, page: Page):
        page.goto(self.BASE_URL)
