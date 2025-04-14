import os

import pytest
from services.manifestservice import ManifestService
from utils import logger


@pytest.mark.skipif(
    "manifestservice" not in pytest.deployed_services,
    reason="manifestservice service is not running on this environment",
)
@pytest.mark.manifestservice
class TestManifestService:
    def test_manifest_service(self):
        """
        Scenario: Create a manifest and verify access
        Steps:
            1. Create a manifest for one user
            2. Verify that the manifest is accessible to the same user
            3. Verify that the manifest is inaccessible to any other user
        """
        manifest_service = ManifestService()
        test_data = [{"object_id": "fake_object_id", "case_id": "fake_case_id"}]

        # Create manifest
        status, resp = manifest_service.post_manifest_for_user(
            "main_account", test_data
        )
        assert status == 200
        assert "filename" in resp

        # Extract file name
        filename = resp["filename"]
        logger.info(f"filename - {filename}")

        # Verify manifest entry accessible to user that created it
        assert filename in manifest_service.get_manifest_for_user("main_account")

        # Verify manifest not accessible to other users
        assert filename not in manifest_service.get_manifest_for_user(
            "indexing_account"
        )
