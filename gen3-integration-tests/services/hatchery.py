import os
import pytest
from playwright.sync_api import expect

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Hatchery:
    def __init__(self, page):
        self.page = page
        # Endpoints
        self.BASE_URL = f"{pytest.root_url}"
        self.WORKSPACE_TAB = f"{self.BASE_URL}/workspace"
        # Locators
        self.workspace_page = "//div[@class='workspace ']"  # Workspace Page
        self.workspace_options = (
            "//div[@class='workspace__options']"  # Workspace Options
        )
        self.generic_card = "//div[@class='workspace-option' and starts-with(h3[@class='workspace-option__title'], '(Generic)')]"  # Juptyer WS Generic Card
        self.workspace_spinner = "//div[@class='workspace__spinner-container']"
        self.workspace_iframe = "//div[@class='workspace__iframe']"
        # Locators inside the workspace iframe
        self.workspace_launcher_frame = 'iframe[title="Workspace"]'  # IFrame workspace
        self.python_command_field = "//div[@class='CodeMirror cm-s-jupyter']"

    def go_to_workspace_page(self):
        """Goes to workspace page and checks if loaded correctly"""
        self.page.goto(self.WORKSPACE_TAB)
        self.page.wait_for_selector(self.workspace_page, state="visible")
        self.page.screenshot(path="output/workspacePage.png", full_page=True)

    def open_jupyter_workspace(self):
        """Launch a jupyter workspace"""
        expect(self.page.locator(self.workspace_options)).to_be_visible()
        # find the workspace option for Juptyer WS to launch
        generic_card = self.page.locator(self.generic_card)
        expect(generic_card).to_be_visible()
        # click the launch button from the juptyer workspace card
        launch_button_xpath = f"{self.generic_card}//button[text()='Launch']"
        launch_button = self.page.locator(launch_button_xpath)
        launch_button.click()
        self.page.screenshot(path="output/jupyterWorkspace.png", full_page=True)
        self.page.wait_for_selector(self.workspace_spinner, state="visible")
        # after launch, workspace takes around 6 mins to load and launc
        self.page.wait_for_selector(
            self.workspace_iframe, state="visible", timeout=324000
        )

    def open_python_kernel(self):
        """perform drs pull in workspace page"""
        # here the frame is on the page, so page.locator is used
        workspace_iframe = self.page.locator(self.workspace_launcher_frame)
        expect(workspace_iframe).to_be_visible
        # here the element is inside the frame, so page.frame_locator is used
        python_kernel_nb = (
            self.page.frame_locator(self.workspace_launcher_frame)
            .get_by_title("Python 3 (ipykernel)")
            .first
        )
        python_kernel_nb.click()
        self.page.wait_for_timeout(3000)
        self.page.screenshot(path="output/pythonKernel.png")
        commandPrompt = self.page.frame_locator(self.workspace_launcher_frame).locator(
            self.python_command_field
        )
        expect(commandPrompt).to_be_visible

    def run_command_notebook(self):
        fill_command = (
            self.page.frame_locator(self.workspace_launcher_frame)
            .get_by_label("notebook content")
            .locator("pre")
        )
        fill_command.click()
        self.page.frame_locator(self.workspace_launcher_frame).get_by_label(
            "notebook content"
        ).get_by_role("textbox").fill("!gen3 --help")
        self.page.frame_locator(self.workspace_launcher_frame).get_by_role(
            "button", name="Run the selected cells and advance"
        ).click()

    def terminate_workspace(self):
        self.page.get_by_role("button", name="Terminate Workspace").click()
        self.page.get_by_role("button", name="Yes").click()
