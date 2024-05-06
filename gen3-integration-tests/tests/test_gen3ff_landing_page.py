import os
import pytest

from cdislogging import get_logger

from pages import gen3ff_landing_page

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.skipif(
    "heal" not in pytest.tested_env, reason="Gen3 FF is deployed only in HEAL"
)
@pytest.mark.portal
@pytest.mark.frontend_framework
class TestGen3FFLandingPage(object):
    def test_home_page_redirection(self, page):
        """
        Scenario: Home page redirects to landing page
        Steps:
            1. Navigate to home page
            2. Browser redirects to landing page
        """
        gen3ff = gen3ff_landing_page.Gen3FFLandingPage()
        page.goto(pytest.root_url)
        gen3ff.is_current_page(page)

    def test_landing_page_buttons(self, page):
        """
        Scenario: Verify buttons on landing page work as expected
        Steps:
            1. Navigate to landing page
            2. Click on the buttons and verify browser is redirected correctly
        """
        gen3ff = gen3ff_landing_page.Gen3FFLandingPage()
        gen3ff.go_to(page)
        gen3ff.check_button(page, "Explore Data", "/discovery")
        gen3ff.go_to(page)
        gen3ff.check_button(page, "Register Your Study", "/study-registration")
        gen3ff.go_to(page)
        gen3ff.check_button(page, "Discover", "/discovery")
        gen3ff.go_to(page)
        gen3ff.check_button(page, "Analyze", "/resource-browser")
        gen3ff.go_to(page)
        gen3ff.check_button(page, "FAQs", "/faqs")
        gen3ff.go_to(page)
        gen3ff.check_button(page, "Tutorials", "/platform_tutorial_videos")
        gen3ff.go_to(page)
        gen3ff.check_button(page, "Resources", "/landing/resource")
