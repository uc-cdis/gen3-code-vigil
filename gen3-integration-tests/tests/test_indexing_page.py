import pytest
import os

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG LEVEL", "info"))


@pytest.mark.portal
class TestIndexingPage:
    def test_indexing_upload(self):
        """
        Scenario: Login and navigate to indexing page and upload dummy manifest
        Steps:
            1. Login with indexing_account user
            2. Navigate to indexing page
            3. Upload dummy manifest and wait for manifest-indexing sower job to finish
            4. Check if the indexd record exists
            5. Chekc if the indexd record hashes exists
        """
        pass

    def test_indexing_downloaded(self):
        """
        Scenario: Login and navigate to indexing page and download indexd manifest
        Steps:
            1. Login with indexing_account user
            2. Navigate to indexing page
            3. Click on Download and wait for manifest-indexing sower job to finish
            4. Send the request to the download url received from step 3
            5. Verify the data
        """
        pass

    def test_indexing_upload_invalid_manifest(self):
        """
        Scenario:
        Steps:
            1. Login with indexing_account user
            2. Navigate to indexing page
            3. Upload invalid manifest and wait for manifest-indexing sower job to finish
            4. Verify that that upload has failed
        """
        pass
