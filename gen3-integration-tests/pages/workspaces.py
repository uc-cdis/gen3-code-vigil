# Workspaces(plural) Page

import pytest
from playwright.sync_api import Page, expect
from utils import logger
from utils.test_execution import screenshot


class WorkspacesPage(object):
    def __init__(self):
        if not pytest.frontend_url:
            raise ValueError("pytest.frontend_url is not configured")

        workspaces_path = pytest.navigation_urls.get("Workspaces", "/Workspaces")
        self.BASE_URL = f"{pytest.root_url}{workspaces_path}"

        # Page locators
        self.READY_CUE = "Launch Local Workspace"
        self.JUPYTER_IFRAME = 'iframe[title="JupyterLite Workspace"]'
        self.PYTHON_LAUNCHER = '[role="button"][title="Python (Pyodide)"]'

        self.NB_CELL_INPUT = ".jp-Cell-inputArea .cm-content"
        self.NB_RUN_CELL_BUTTON = '[data-jp-item-name="run"] button'
        self.NB_CELL_OUTPUT = ".jp-OutputArea-output"

    def go_to(self, page: Page):
        """Goes to the workspaces page and checks if it has loaded correctly"""
        page.goto(self.BASE_URL)
        expect(page.get_by_text(self.READY_CUE, exact=True)).to_be_visible()
        screenshot(page, "WorkspacesPage")

    def launch_workspaces(self, page: Page):
        """Launches the workspaces free jupyter lite version"""
        expect(page.get_by_text(self.READY_CUE, exact=True)).to_be_visible()
        logger.info("Launching workspaces(plural)")
        page.get_by_text(self.READY_CUE, exact=True).click()
        # Wait for JupyterLite iframe
        iframe = page.locator(self.JUPYTER_IFRAME)
        expect(iframe).to_be_visible(timeout=60_000)
        # Access JupyterLite iframe
        jupyter = page.frame_locator(self.JUPYTER_IFRAME)
        # Wait for Python launcher
        python_launcher = jupyter.locator(self.PYTHON_LAUNCHER).first

        expect(python_launcher).to_be_visible(timeout=60_000)

        logger.info("JupyterLite workspaces loaded")
        screenshot(page, "WorkspacesLaunched")

    def open_python_pyodide_notebook(self, page: Page):
        """Open Python Pyodide notebook in JupyterLite."""
        jupyter = page.frame_locator(self.JUPYTER_IFRAME)
        python_launcher = jupyter.locator(self.PYTHON_LAUNCHER).first
        expect(python_launcher).to_be_visible(timeout=60_000)

        logger.info("Opening Python Pyodide notebook")
        python_launcher.click()
        # Wait for notebook to launch
        page.wait_for_timeout(10000)
        screenshot(page, "PyodideNotebook")

    def run_pyodide_command_in_notebook(self, page: Page, command: str):
        """Run a command in the JupyterLite Python Pyodide notebook."""
        jupyter = page.frame_locator(self.JUPYTER_IFRAME)
        command_input = jupyter.locator(self.NB_CELL_INPUT).last
        expect(command_input).to_be_visible(timeout=120_000)

        command_input.click()
        command_input.press_sequentially(command)
        screenshot(page, "NotebookCellInput")

        run_button = jupyter.locator(self.NB_RUN_CELL_BUTTON)
        expect(run_button).to_be_visible(timeout=60_000)
        run_button.click()
        output = jupyter.locator(self.NB_CELL_OUTPUT).last
        output.wait_for(state="visible", timeout=120_000)
        screenshot(page, "NotebookCellOutput")

        return output.text_content()
