"""
Hatchery Test
"""
import os
import pytest

from cdislogging import get_logger

from pages.login import LoginPage
from pages.workspace import WorkspacePage

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.workspace
class TestWorkspacePage:
    def test_workspace_drs_pull(self, page):
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
        login_page.go_to(page)
        """login with mainAcct user"""
        login_page.login(page)
        """navigates to workspace page and sees workspace_options"""
        workspace_page.go_to(page)
        """launches the workspace jupyter notebook"""
        workspace_page.open_jupyter_workspace(page)
        """opens python kernel in notebook"""
        workspace_page.open_python_kernel(page)
        """executes gen3 --help command"""
        workspace_page.run_command_notebook(page)
        """terminates the workspace after executing the command"""
        workspace_page.terminate_workspace(page)
