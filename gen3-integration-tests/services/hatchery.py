import os
import pytest
from playwright.sync_api import Page, expect

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Hatchery(object):
    def __init__(self):
        # Endpoints
        self.BASE_URL = f"{pytest.root_url}"
        self.WORKSPACE_TAB = f"{self.BASE_URL}/workspace"
        # Locators
        self.workspace_page = ".workspace"  # Workspace Page
        self.workspace_options = ".workspace_options"  # Workspace Options
        self.generic_card = (
            "//div[contains(text(), /^(Generic)/)]"  # Juptyer WS Generic Card
        )
        self.launch_button = ".workspace-option__button"  # Launch Button
        self.workspace_iframe_locator = 'iframe[title="Workspace"]'  # IFrame workspace

    def go_to_workspace_page(self, page: Page):
        """Goes to workspace page and checks if loaded correctly"""
        page.goto(self.WORKSPACE_TAB)
        expect(page.locator(self.workspace_page)).to_be_visible

    def open_jupyter_workspace(self, page: Page):
        """Launch a jupyter workspace"""
        expect(page.locator(self.workspace_options)).to_be_visible
        # find the workspace option for Juptyer WS to launch
        generic_card = page.locator(self.generic_card)
        # click the launch button from the juptyer workspace card
        generic_card.page_locator(self.launch_button).click()

    def open_python_kernel(self, page: Page):
        """perform drs pull in workspace page"""
        workspace_iframe = page.frame_locator(self.workspace_iframe_locator)
        expect(workspace_iframe).to_be_visible
        python_kernel_nb = (
            page.frame_locator(self.workspace_iframe_locator)
            .get_by_title("Python 3 (ipykernel)")
            .first
        )
        python_kernel_nb.click()
        expect(
            page.frame_locator(self.workspace_iframe_locator).get_by_label(
                "notebook content"
            )
        ).to_be_visible

    def run_command_notebook(self, page: Page):
        fill_command = (
            page.frame_locator(self.workspace_iframe_locator)
            .get_by_label("notebook content")
            .locator("pre")
        )
        fill_command.click()
        page.frame_locator(self.workspace_iframe_locator).get_by_label(
            "notebook content"
        ).get_by_role("textbox").fill("!gen3 drs-pull manifest <manifest-name>")
        page.frame_locator(self.workspace_iframe_locator).get_by_role(
            "button", name="Run the selected cells and advance"
        ).click()

    def terminate_workspace(self, page: Page):
        page.get_by_role("button", name="Terminate Workspace").click()
        page.get_by_role("button", name="Yes").click()
