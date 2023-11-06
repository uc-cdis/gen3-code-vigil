import pytest
from playwright.sync_api import Page, expect


class Hatchery(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}"
        self.WORKSPACE_TAB = f"{self.BASE_URL}/workspace"

    def go_to_workspace_page(self, page: Page):
        """Goes to workspace page and checks if loaded correctly"""
        page.goto(self.WORKSPACE_TAB)
        workspace_page = page.locator(".workspace")
        expect(workspace_page).to_be_visible

    def open_jupyter_workspace(self, page: Page):
        """Launch a jupyter workspace"""
        workspace_options = page.locator(".workspace_options")
        expect(workspace_options).to_be_visible
        # find the workspace option for Juptyer WS to launch
        generic_card = page.locator("//div[contains(text(), /^(Generic)/)]")
        # click the launch button from the juptyer workspace card
        launch_button = generic_card.get_by_role("button", name="Launch")
        launch_button.click()

    def open_python_kernel(self, page: Page):
        """perform drs pull in workspace page"""
        workspace_iframe = page.frame_locator('iframe[title="Workspace"]')
        expect(workspace_iframe).to_be_visible
        python_kernel_nb = (
            page.frame_locator('iframe[title="Workspace"]')
            .get_by_title("Python 3 (ipykernel)")
            .first
        )
        python_kernel_nb.click()
        expect(
            page.frame_locator('iframe[title="Workspace"]').get_by_label(
                "notebook content"
            )
        ).to_be_visible

    def run_command_notebook(self, page: Page):
        fill_command = (
            page.frame_locator('iframe[title="Workspace"]')
            .get_by_label("notebook content")
            .locator("pre")
        )
        fill_command.click()
        page.frame_locator('iframe[title="Workspace"]').get_by_label(
            "notebook content"
        ).get_by_role("textbox").fill("!gen3 drs-pull manifest <>manifest-name")
        page.frame_locator('iframe[title="Workspace"]').get_by_role(
            "button", name="Run the selected cells and advance"
        ).click()

    def terminate_workspace(self, page: Page):
        page.get_by_role("button", name="Terminate Workspace").click()
        page.get_by_role("button", name="Yes").click()
