"""
RAS Passports
"""

import os

import pytest
from cdislogging import get_logger
from services.drs import Drs
from services.fence import Fence
from services.indexd import Indexd

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))

indexd_files = {
    "test_with_ras_permission": {
        "acl": [],
        "authz": ["/programs/phs000000.c11"],
        "file_name": "ras_passport_test_file",
        "hashes": {"md5": "587efb5d96f695710a8df9c0dbb96eb0"},
        "size": 15,
        "urls": [
            "s3://cdis-presigned-url-test/testdata",
            "gs://cdis-presigned-url-test/testdata",
        ],
    },
}


@pytest.mark.skipif(
    "nightly-build" not in pytest.hostname,
    reason="Test is being run for ras auth which is only on nightly-build namespaces",
)
@pytest.mark.skipif(
    "indexd" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.indexd
@pytest.mark.fence
@pytest.mark.ras
class TestRasPassport:
    @classmethod
    def setup_class(cls):
        cls.indexd = Indexd()
        cls.fence = Fence()
        cls.drs = Drs()
        cls.variables = {}
        cls.variables["created_indexd_dids"] = []

        # Adding file to IndexD
        for key, val in indexd_files.items():
            indexd_record = cls.indexd.create_records(records={key: val})
            cls.variables["created_indexd_dids"].append(indexd_record[0]["did"])

    # @classmethod
    # def teardown_class(cls):
    # Deleting indexd records
    # cls.indexd.delete_records(cls.variables["created_indexd_dids"])

    def test_get_drs_presigned_url(self):
        """
        Scenario: get drs presigned-url
        Steps:
            1. Get the drs presigned url for the created ras indexd record
            2. Validate the content of the file.
        """
        signed_url_res = self.drs.get_drs_signed_url(
            file=indexd_files["test_with_ras_permission"]
        )
        self.fence.check_file_equals(
            signed_url_res=signed_url_res.json(),
            file_content="Hi Zac!\ncdis-data-client uploaded this!\n",
        )
