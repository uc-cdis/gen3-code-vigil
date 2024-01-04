import os
import pytest

from cdislogging import get_logger
from playwright.sync_api import expect

from pages.home import HomePage

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.portal
class TestHomePage:
    def test_home_page_navigation(self, page):
        """
        Steps:
        1. Navigate to home page and verify that landing page is as expected.
        """
        # Go to home page
        home_page = HomePage()
        home_page.go_to(page)
        expect(page).to_have_url(home_page.landing_page())
