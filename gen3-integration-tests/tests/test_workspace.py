"""
Hatchery Test
"""

import pytest
from pages.login import LoginPage
from pages.workspace import WorkspacePage
from utils import logger
from utils.test_execution import screenshot


@pytest.fixture()
def page_setup(page):
    yield page
    workspace = WorkspacePage()
    if page.locator(workspace.TERMINATE_BUTTON).is_visible():
        workspace.terminate_workspace(page)
        screenshot(page, "WorkspaceTerminatedInTearDown")
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
@pytest.mark.workspace
@pytest.mark.portal
class TestWorkspacePage:
    def test_workspace_drs_pull(self, page_setup):
        """
        Scenario: Workspace DRS Pull
        Steps:
            1. Login with main_acct (cdis.autotest) user
            2. Launch workspace
            3. Launch Jupyter notebook and execute gen3 command

        We are verifying successful launch of workspace service by launching generic notebook
        and execute gen3 command. We need would need to update the test to export the manifest from
        exploration page and execute the manifest gen3 commands.
        """
        workspace_page = WorkspacePage()
        login_page = LoginPage()
        logger.info("# Logging in with mainAcct")
        login_page.go_to(page_setup)
        """login with mainAcct user"""
        login_page.login(page_setup)
        """navigates to workspace page and sees workspace_options"""
        workspace_page.go_to(page_setup)
        """launches the workspace jupyter notebook"""
        workspace_page.launch_workspace(page_setup)
        """opens python kernel in notebook"""
        workspace_page.open_python_notebook(page_setup)
        command = "!pip install -U gen3==4.24.1"
        logger.info(f"Running in jupyter notebook: {command}")
        result = workspace_page.run_command_in_notebook(page_setup, command)
        logger.info(
            "Running command in jupyter notebook: !gen3 --help"
        )  # default command
        result = workspace_page.run_command_in_notebook(page_setup)
        logger.info(f"Result: {result}")
        """terminates the workspace after executing the command"""
        workspace_page.terminate_workspace(page_setup)
