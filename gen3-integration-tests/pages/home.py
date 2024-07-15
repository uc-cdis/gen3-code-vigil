# Home page
import os
import pytest

from utils import logger
from playwright.sync_api import Page


class HomePage(object):
    def __init__(self):
        self.BASE_URL = pytest.root_url_portal

        # Locators
        self.SUMMARY, self.CARDS = self.home_page_details(pytest.tested_env)

    def go_to(self, page: Page):
        page.goto(self.BASE_URL)

    def home_page_details(self, env):
        if "pandemicresponsecommons" in env or "covid19" in env:
            return (".covid19-dashboard", ".covid19-dashboard_counts")
        elif "niaid" in env:
            return (".index-page__introduction", ".g3-button")
        elif "healdata" in env or "qa-heal" in env or "brh" in env:
            return (".discovery-header", ".discovery-studies-container")
        else:
            return (".introduction", ".index-button-bar__thumbnail-button")
