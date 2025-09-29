import os
from pathlib import Path

import allure
import pytest


class TestAttachCombinedLog(object):

    @allure.title("📄 Test Run Logs")
    def test_attach_combined_log():
        # Only run this on the master process
        if os.getenv("PYTEST_XDIST_WORKER"):
            pytest.skip("Skip on xdist workers — will only run on master.")

        log_path = Path("output/test_logs.log")
        if log_path.exists():
            with log_path.open("r") as f:
                allure.attach(
                    f.read(),
                    name="Full Run Combined Log",
                    attachment_type=allure.attachment_type.TEXT,
                )
        else:
            pytest.skip("Combined log file not found.")
