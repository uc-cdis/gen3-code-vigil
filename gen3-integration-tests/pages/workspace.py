# Workspace Page
import pytest

from playwright.sync_api import expect, Page

from utils import logger
from utils.test_execution import screenshot


class WorkspacePage(object):
    def __init__(self):
        # Endpoints
        self.BASE_URL = f"{pytest.root_url_portal}/workspace"
        # Locators
        self.READY_CUE = "//div[@class='workspace ']"  # Workspace Page
        self.WORKSPACE_OPTIONS = (
            "//div[@class='workspace__options']"  # Workspace Options
        )
        self.LAUNCH_FIRST_WORKSPACE = (
            "(//div[@class='workspace-option'])[1]/button[text()='Launch']"
        )
        self.WORKSPACE_IFRAME = 'iframe[title="Workspace"]'  # Workspace iframe
        # Locators inside the workspace iframe
        self.NEW_NB = (
            "//button[@id='new-dropdown-button']"  # Dropdown to create new notebook
        )
        self.NEW_NB_PYTHON = (
            "//li[@id='kernel-python3']"  # Dropdown selection to create Python notebook
        )
        self.NB_CELL_INPUT = (
            "//div[@aria-label='Edit code here']"  # Notebook code cell input
        )
        self.NB_RUN_CELL_BUTTON = (
            "//button[@aria-label='Run']"  # Notebook button to run cell and select next
        )
        self.NB_CELL_OUTPUT = "//div[@class='output_subarea output_text output_stream output_stdout']//pre"  # output after run command
        self.TERMINATE_BUTTON = (
            "//button[contains(text(),'Terminate Workspace')]"  # terminate nb button
        )
        self.YES_BUTTON = "//span[contains(text(),'Yes')]"  # terminate 'yes' button

    def go_to(self, page: Page):
        """Goes to workspace page and checks if loaded correctly"""
        page.goto(self.BASE_URL)
        page.wait_for_selector(self.READY_CUE, state="visible")
        screenshot(page, "WorkspacePage")

    def assert_page_loaded(self, page: Page):
        """Checks if workspace page loaded successfully"""
        page.wait_for_selector(self.READY_CUE, state="visible")
        screenshot(page, "WorkspacePageLoaded")

    def launch_workspace(self, page: Page, name: str = ""):
        """
        Launch the workspace with the given name
        Launches the first available one if `name` is not specified
        """
        logger.info("Increasing capacity to speed up the launch")
        expect(page.locator(self.WORKSPACE_OPTIONS)).to_be_visible()
        # launch the specified workspace option if the name is provided
        logger.info(f"Launching workspace {name}")
        if name:
            launch_button_xpath = f"//h3[text()='{name}']/parent::div[@class='workspace-option']/button[text()='Launch']"
        # launch the first available option if the name is not provided
        else:
            launch_button_xpath = self.LAUNCH_FIRST_WORKSPACE
        logger.debug(f"Xpath: {launch_button_xpath}")
        launch_button = page.locator(launch_button_xpath)
        launch_button.click()
        screenshot(page, "WorkspaceLaunching")
        # workspace can take a while to launch
        page.frame_locator(self.WORKSPACE_IFRAME).locator(
            "//div[@aria-label='Top Menu']"
        ).wait_for(timeout=600000)

    def open_python_notebook(self, page: Page):
        """Open Python notebook in the workspace"""
        # here the frame is on the page, so page.locator is used
        workspace_iframe = page.locator(self.WORKSPACE_IFRAME)
        expect(workspace_iframe).to_be_visible
        python_nb = page.frame_locator(self.WORKSPACE_IFRAME).locator(self.NEW_NB)
        python_nb.click()
        python_kernel_nb = page.frame_locator(self.WORKSPACE_IFRAME).locator(
            self.NEW_NB_PYTHON
        )
        python_kernel_nb.click()
        command_prompt = page.frame_locator(self.WORKSPACE_IFRAME).locator(
            self.NB_CELL_INPUT
        )
        command_prompt.wait_for(state="visible", timeout=60000)
        screenshot(page, "PythonNotebook")

    def run_command_in_notebook(self, page: Page, command: str = "!gen3 --help"):
        command_input = (
            page.frame_locator(self.WORKSPACE_IFRAME).locator(self.NB_CELL_INPUT).last
        )
        command_input.press_sequentially(command)
        screenshot(page, "NotebookCellInput")
        page.frame_locator(self.WORKSPACE_IFRAME).locator(
            self.NB_RUN_CELL_BUTTON
        ).click()
        output = (
            page.frame_locator(self.WORKSPACE_IFRAME).locator(self.NB_CELL_OUTPUT).last
        )
        output.wait_for(state="visible")
        screenshot(page, "NotebookCellOutput")
        return output.text_content()

    def terminate_workspace(self, page: Page):
        page.locator(self.TERMINATE_BUTTON).click()
        page.locator(self.YES_BUTTON).click()
        page.locator(self.WORKSPACE_OPTIONS).wait_for(timeout=600000)
