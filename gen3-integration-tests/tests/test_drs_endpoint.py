"""
DRS Endpoint
"""

import os
import pytest
import uuid

from cdislogging import get_logger
from services.indexd import Indexd
from services.fence import Fence

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))

indexd_files = {
    "allowed": {
        "filename": "test_valid",
        "link": "s3://cdis-presigned-url-test/testdata",
        "md5": "73d643ec3f4beb9020eef0beed440ad0",
        "acl": ["jenkins"],
        "size": 9,
    },
    "not_allowed": {
        "filename": "test_not_allowed",
        "link": "s3://cdis-presigned-url-test/testdata",
        "md5": "73d643ec3f4beb9020eef0beed440ad0",
        "acl": ["acct"],
        "size": 9,
    },
    "no_link": {
        "filename": "test_no_link",
        "md5": "73d643ec3f4beb9020eef0beed440ad0",
        "acl": ["jenkins"],
        "size": 9,
    },
    "http_link": {
        "filename": "test_procol",
        "link": "http://cdis-presigned-url-test/testdata",
        "md5": "73d643ec3f4beb9020eef0beed440ad0",
        "acl": ["jenkins"],
        "size": 9,
    },
    "invalid_protocol": {
        "filename": "test_invalid_protocol",
        "link": "s2://cdis-presigned-url-test/testdata",
        "md5": "73d643ec3f4beb9020eef0beed440ad0",
        "acl": ["jenkins"],
        "size": 9,
    },
}


@pytest.mark.fence
class TestDrsEndpoints:
    indexd = Indexd()
    fence = Fence()
    variables = {}
    variables["created_indexd_dids"] = []

    @classmethod
    def setup_class(cls):
        # Removing test indexd records if they exist
        cls.indexd.delete_records(cls.variables["created_indexd_dids"])

        # Adding indexd files
        for key, val in indexd_files.items():
            indexd_record = cls.indexd.create_records(records={key: val})
            cls.variables["created_indexd_dids"].append(indexd_record[0]["did"])

    @classmethod
    def teardown_class(cls):
        # Removing test indexd records
        cls.indexd.delete_records(cls.variables["created_indexd_dids"])

    def test_get_drs_object(self):
        """
        Scenario: get drs object
        Steps:
            1.
        """
