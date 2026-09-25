"""
This is Workspaces(plural) test
"""

import os

import pytest
from pages.login import LoginPage
from pages.workspaces import WorkspacesPage
from utils import logger
from utils.test_execution import screenshot


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
    not any(x in os.getenv("SOURCE_CONFIG", "") for x in ("pdp-commons", "vadcprod")),
    reason="This test is configured to run only on PDP and vpodc commons",
)
@pytest.mark.workspaces
@pytest.mark.frontend
class TestWorkspacePage:
    def test_launch_workspace(self, page_setup):
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
        """navigates to workspaces(plural) page and sees workspace_options"""
        workspaces_page.go_to(page_setup)
