import os
import pytest

from cdislogging import get_logger

from pages import home, login

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.portal
class TestHomePage:
    def test_home_page_navigation(self, page):
        """
        Scenario: Login to Home Page and verify summary & cards elements
        Steps:
            1. Navigate to home page
            2. Login using the main account
            3. Verify the summary and cards are as expected
            4. Logout
        """
        # Go to home page
        home_page = home.HomePage()
        home_page.go_to(page)
        # Login
        login_page = login.LoginPage()
        login_page.go_to(page)
        login_page.login(page)
        # Verify summary and cards elements
        assert page.locator(home_page.SUMMARY) is not None
        assert page.locator(home_page.CARDS) is not None
        # Logout
        login_page.logout(page)
