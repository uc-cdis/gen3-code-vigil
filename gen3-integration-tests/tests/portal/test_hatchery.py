"""
Hatchery tests
1.
"""

import os
import pytest

from cdislogging import get_logger
import utils.gen3_admin_tasks as gat

from services.login import Login
from services.hatchery import Hatchery

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class TestHatchery:
    def test_workspace_drc_pull(self):
        hatchery = Hatchery()
        login = Login()
        logger.info("# Logging in with mainAcct")
        login.go_to_login_page()
        login.user_login()

        hatchery.go_to_workspace_page()
        hatchery.open_jupyter_workspace()
        hatchery.open_python_kernel()
        hatchery.run_command_notebook()
        hatchery.terminate_workspace()
