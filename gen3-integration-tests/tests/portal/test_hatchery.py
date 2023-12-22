"""
Hatchery Test
"""
import os
import pytest

from cdislogging import get_logger
import utils.gen3_admin_tasks as gat

from playwright.sync_api import Page

from services.login import LoginPage
from services.hatchery import Hatchery

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.hatchery
class TestHatchery:
    def test_workspace_drs_pull(self, browser: Page):
        hatchery = Hatchery(browser)
        login_page = LoginPage(browser)
        logger.info("# Logging in with mainAcct")
        login_page.go_to_page()
        """login with mainAcct user"""
        login_page.login()
        """navigates to workspace page and sees workspace_options"""
        hatchery.go_to_workspace_page()
        """launches the workspace Generic notebook"""
        # hatchery.open_jupyter_workspace()
        """opens python kernel in notebook"""
        hatchery.open_python_kernel()
        """executes gen3 --help command"""
        hatchery.run_command_notebook()
        """terminates the workspace after executing the command"""
        hatchery.terminate_workspace()
