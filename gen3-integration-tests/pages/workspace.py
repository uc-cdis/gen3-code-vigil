# Workspace Page
import os
import pytest

from cdislogging import get_logger

from playwright.sync_api import expect, Page

from utils.test_execution import screenshot

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class WorkspacePage(object):
    def __init__(self):
        # Endpoints
        self.BASE_URL = f"{pytest.root_url_portal}/workspace"
        # Locators
        self.READY_CUE = "//div[@class='workspace ']"  # Workspace Page
        self.WORKSPACE_OPTION = (
            "//div[@class='workspace__options']"  # Workspace Options
        )
        self.NOTEBOOK_CARD = (
            "(//div[@class='workspace-option'])[1]"  # workspace option first card
        )
        self.WORKSPACE_SPINNER = (
            "//div[@class='workspace__spinner-container']"  # workspace loading spinner
        )
        self.WORKSPACE_IFRAME = "//div[@class='workspace__iframe']"
        # Locators inside the workspace iframe
        self.WORKSPACE_LAUNCHER_FRAME = 'iframe[title="Workspace"]'  # IFrame workspace
        self.NEW_PYTHON_NB = (
            "//button[@id='new-dropdown-button']"  # Dropdown to select new notebook
        )
        self.PYTHON_NB = "//a[@title='Create a new notebook with Python 3 (ipykernel)']"  # dropdown box python nb selection
        self.PYTHON_COMMAND_FIELD = (
            "//div[@aria-label='Edit code here']"  # command input field
        )
        self.RUN_COMMAND_BUTTON = (
            "//button[@title='run cell, select below']"  # run command button
        )
        self.RUN_COMMAND_OUTPUT = "//div[@class='output_subarea output_text output_stream output_stdout']//pre"  # output after run command
        self.TERMINATE_BUTTON = (
            "//button[contains(text(),'Terminate Workspace')]"  # terminate nb button
        )
        self.YES_BUTTON = "//span[contains(text(),'Yes')]"  # terminate 'yes' button

    def go_to(self, page: Page):
        """Goes to workspace page and checks if loaded correctly"""
        page.goto(self.BASE_URL)
        page.wait_for_selector(self.READY_CUE, state="visible")
        screenshot(page, "workspacePage")

    def open_jupyter_workspace(self, page: Page):
        """Launch a jupyter workspace"""
        expect(page.locator(self.WORKSPACE_OPTION)).to_be_visible()
        # find the workspace option for Juptyer WS to launch
        generic_card = page.locator(self.NOTEBOOK_CARD)
        expect(generic_card).to_be_visible()
        # click the launch button from the juptyer workspace card
        launch_button_xpath = f"{self.NOTEBOOK_CARD}//button[text()='Launch']"
        launch_button = page.locator(launch_button_xpath)
        launch_button.click()
        screenshot(page, "jupyterWorkspace")
        page.wait_for_selector(self.WORKSPACE_SPINNER, state="visible")
        # after launch, workspace takes around 6 mins to load and launc
        page.wait_for_selector(self.WORKSPACE_IFRAME, state="visible", timeout=600000)

    def open_python_kernel(self, page: Page):
        """perform drs pull in workspace page"""
        # here the frame is on the page, so page.locator is used
        workspace_iframe = page.locator(self.WORKSPACE_LAUNCHER_FRAME)
        expect(workspace_iframe).to_be_visible
        python_nb = page.frame_locator(self.WORKSPACE_LAUNCHER_FRAME).locator(
            self.NEW_PYTHON_NB
        )
        python_nb.click()
        python_kernel_nb = page.frame_locator(self.WORKSPACE_LAUNCHER_FRAME).locator(
            self.PYTHON_NB
        )
        python_kernel_nb.click()
        commandPrompt = page.frame_locator(self.WORKSPACE_LAUNCHER_FRAME).locator(
            self.PYTHON_COMMAND_FIELD
        )
        commandPrompt.wait_for(timeout=300000, state="visible")
        screenshot(page, "pythonKernel")

    def run_command_notebook(self, page: Page):
        screenshot(page, "gen3CommandOutput1")
        command_input = page.frame_locator(self.WORKSPACE_LAUNCHER_FRAME).locator(
            self.PYTHON_COMMAND_FIELD
        )
        command_input.press_sequentially("!gen3 --help")
        screenshot(page, "fillCommand")
        page.frame_locator(self.WORKSPACE_LAUNCHER_FRAME).locator(
            self.RUN_COMMAND_BUTTON
        ).click()
        screenshot(page, "gen3CommandOutput1")
        output = page.frame_locator(self.WORKSPACE_LAUNCHER_FRAME).locator(
            self.RUN_COMMAND_OUTPUT
        )
        output.wait_for(timeout=300000, state="visible")
        screenshot(page, "gen3CommandOutput")

    def terminate_workspace(self, page: Page):
        # page.get_by_role("button", name="Terminate Workspace").click()
        page.locator(self.TERMINATE_BUTTON).click()
        # page.get_by_role("button", name="Yes").click()
        page.locator(self.YES_BUTTON).click()
