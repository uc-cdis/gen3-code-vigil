"""
Hatchery tests
1.
"""

import os
import pytest

from cdislogging import get_logger
import utils.gen3_admin_tasks as gat

from playwright.sync_api import sync_playwright, expect, Page

from services.login import LoginPage
from services.hatchery import Hatchery

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.hatchery
class TestHatchery:
    def test_workspace_drs_pull(self, page: Page):
        hatchery = Hatchery(page)
        login_page = LoginPage(page)
        logger.info("# Logging in with mainAcct")
        login_page.go_to_page()
        login_page.login()
        login_page.handle_popup()
        hatchery.go_to_workspace_page()
        hatchery.open_jupyter_workspace()
        hatchery.open_python_kernel()
        hatchery.run_command_notebook()
        hatchery.terminate_workspace()
