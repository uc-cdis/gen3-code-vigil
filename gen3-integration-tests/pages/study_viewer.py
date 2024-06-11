import pytest
import os
from utils import logger
import utils.gen3_admin_tasks as gat

from utils.test_execution import screenshot
from playwright.sync_api import Page, expect

index = gat.get_study_viewer_index(pytest.namespace)


class StudyViewerPage(object):
    def __init__(self):
        # Endpoints
        self.BASE_URL = f"{pytest.root_url_portal}/study-viewer/"
        self.STUDY_VIEWER_URL = f"{self.BASE_URL}/{index}"

        # Locators
        self.STUDY_VIEWER_DIV = ("//div[@class='study-viewer']",)

        self.LOGINRA_BUTTON = "//button[contains(text(), 'Login to Request Access')]"

    def go_to(self, page: Page):
        page.goto(self.STUDY_VIEWER_URL)
