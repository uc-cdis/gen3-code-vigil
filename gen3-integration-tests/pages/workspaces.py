# Workspaces(plural) Page

import pytest
from playwright.sync_api import Page, expect
from utils import logger
from utils.test_execution import screenshot


class WorkspacesPage(object):
    def __init__(self):
        # Endpoints
        if pytest.frontend_url:
            workspace_path = pytest.navigation_urls.get("Workspace", "/Workspaces")
