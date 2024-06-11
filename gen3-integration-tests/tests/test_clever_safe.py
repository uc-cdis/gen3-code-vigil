"""
CLEVER SAFE Presigned URL
"""

import os
import pytest

from cdislogging import get_logger
from services.indexd import Indexd
from services.fence import Fence

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))

indexed_files = {
    "clever_safe_test_file1": {
        "filename": "test",
        "link": "s3://fence-cleversafe-test/test",
        "md5": "d8e8fca2dc0f896fd7cb4cb0031ba249",
        "acl": ["QA"],
        "size": 5,
    },
}


@pytest.mark.indexd
class TestCleverSafe:
    indexd = Indexd()
    fence = Fence()

    def setup_method(self):
        # Removing test indexd records if they exist
        self.indexd.delete_file_indices(records=indexed_files)

        # Adding indexd files used to test signed urls
        for key, val in indexed_files.items():
            indexd_record = self.indexd.create_files(files={key: val})
            indexed_files[key]["did"] = indexd_record[0]["did"]
            indexed_files[key]["rev"] = indexd_record[0]["rev"]

    def teardown_method(self):
        logger.info("Deleting Indexd Records")
        self.indexd.delete_file_indices(records=indexed_files)

    @pytest.mark.wip("File is not accessbile, need to check")
    def test_simple_clever_safe_presigner_url(self):
        """
        Scenario: Simple CleverSafe PreSigned URL test
        Steps:
            1. Set environment variable NODE_TLS_REJECT_UNAUTHORIZED to '0'.
            2. Create presigned url for clever_safe_test_file1.(Indexd records created as part of setup)
            3. File should be downloaded using the presigned url.
        """
        os.environ["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"

        # Create Signed URLs
        signed_url_res = self.fence.createSignedUrl(
            id=indexed_files["clever_safe_test_file1"]["did"],
            user="main_account",
            expectedStatus=200,
        )

        # Verify signed url is created
        assert (
            "url" in signed_url_res.keys()
        ), "Could not find url keyword in signed url"

        # Verify the contents of file downloaded using signed url
        self.fence.check_file_equals(signed_url_res, "test\n")
