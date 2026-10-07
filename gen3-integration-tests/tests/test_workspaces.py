"""
This is Workspaces(plural) test
"""

import os
import textwrap

import pytest
from pages.login import LoginPage
from pages.workspaces import WorkspacesPage
from utils import logger


@pytest.fixture()
def page_setup(page):
    yield page
    page.close()


@pytest.mark.skipif(
    "ambassador" not in pytest.deployed_services,
    reason="ambassador service is not running on this environment",
)
@pytest.mark.skipif(
    "wts" not in pytest.deployed_services,
    reason="wts service is not running on this environment",
)
@pytest.mark.skipif(
    "hatchery" not in pytest.deployed_services,
    reason="hatchery service is not running on this environment",
)
@pytest.mark.skipif(
    not (
        any(x in os.getenv("SOURCE_CONFIG", "") for x in ("pdp-commons", "vadcprod"))
        or os.getenv("NAMESPACE", "") == "nightly-build-ff"
    ),
    reason="Currently the Workspaces is only on PDP/vadc commons or nightly-build-ff",
)
@pytest.mark.skipif(
    "frontend-framework" not in pytest.deployed_services,
    reason="WorkSpaces(plural) runs only frontend-framework",
)
@pytest.mark.workspaces
@pytest.mark.frontend
class TestWorkspacesPage:
    def test_launch_and_run_command_in_workspaces(self, page_setup):
        """
        Scenario: Launch the new jupyterlite workspace from workspaces page
        Steps:
            1. Login with main_acct (main_account) user
            2. Launch workspaces
            3. Launch Jupyter lite pyodide notebook and install 'requests' Python library

        We are verifying successful launch of the free version of the jupyter lite workspace from the workspaces page by
        launching the python(pyodide) notebook and install the 'requests' library. Currently, the Jupyter lite notebook
        comes only in pdp and vadc commons.
        """
        workspaces_page = WorkspacesPage()
        login_page = LoginPage()
        logger.info("# Logging in with mainAcct")
        login_page.go_to(page_setup)
        """login with mainAcct user"""
        login_page.login(page_setup)
        """navigates to workspaces(plural) page"""
        workspaces_page.go_to(page_setup)
        """launches the workspaces jupyter lite free version"""
        workspaces_page.launch_workspaces(page_setup)
        """opens the python(pyodide) notebook"""
        workspaces_page.open_python_pyodide_notebook(page_setup)
        # Command to run in the python pyodide notebook.
        command = textwrap.dedent("""\
            import micropip
            await micropip.install("requests")
            import requests
            print(requests.__version__)
            """)

        """running the python pyodide command"""
        result = workspaces_page.run_pyodide_command_in_notebook(page_setup, command)
        logger.info("Running command in jupyter lite python pyodide notebook")
        logger.info(f"Result: {result}")
