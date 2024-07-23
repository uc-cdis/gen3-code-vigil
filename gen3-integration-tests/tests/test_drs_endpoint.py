"""
DRS Endpoint
"""

import os
import pytest

from services.indexd import Indexd
from services.drs import Drs
from services.fence import Fence

from cdislogging import get_logger
from packaging.version import Version

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))

indexd_files = {
    "allowed": {
        "file_name": "test_valid",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["jenkins"],
        "size": 9,
    },
    "not_allowed": {
        "file_name": "test_not_allowed",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["acct"],
        "size": 9,
    },
    "invalid_protocol": {
        "file_name": "test_invalid_protocol",
        "urls": ["s2://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["jenkins"],
        "size": 9,
    },
}


@pytest.mark.fence
class TestDrsEndpoints:
    indexd = Indexd()
    drs = Drs()
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
            1. Get the drs object for indexd record (allowed).
            2. Get the drs object and compare the records are same.
        """
        drs_record = self.drs.get_drs_object(file=indexd_files["allowed"])
        res = self.drs.get_drs_object(drs_record.json())
        assert (
            drs_record.json() == res.json()
        ), f"Expected same values but got different.\ndrs_record: {drs_record}\nResponse: {res}"

    def test_get_drs_no_record_found(self):
        """
        Scenario: get drs no record found
        Steps:
            1. Get the drs object for indexd record (not_allowed).
            2. Get the drs object usign the response object in step 1. Drs object shouldn't be returned.
        """
        drs_record = self.drs.get_drs_object(file=indexd_files["not_allowed"])
        res = self.drs.get_drs_object(drs_record)
        assert (
            res.status_code == 404
        ), f"Expected status code 404, but got {res.status_code}"

    def test_get_drs_presigned_url(self):
        """
        Scenario: get drs presigned-url
        Steps:
            1. Get the drs presgined url for indexd record (allowed).
            2. Validate the content of the file checkout.
        """
        signed_url_res = self.drs.get_drs_signed_url(file=indexd_files["allowed"])
        self.fence.check_file_equals(
            signed_url_res=signed_url_res.json(),
            file_content="Hi Zac!\ncdis-data-client uploaded this!\n",
        )

    def test_get_drs_invalid_access_id(self):
        """
        Scenario: get drs invalid access id
        Steps:
            1. Get the drs presgined url for indexd record (invalid_protocol).
            2. Validate the response is 400 since the s2 protocol used here is not supported.
        """
        signed_url_res = self.drs.get_drs_signed_url(
            file=indexd_files["invalid_protocol"]
        )
        # The specified protocol s2 is not supported (part of the signed_url_res.content) so status is 400
        assert (
            signed_url_res.status_code == 400
        ), f"Expected status 400 but got {signed_url_res.status_code}"

    def test_get_drs_presigned_url_no_auth_header(self):
        """
        Scenario: get drs presigned-url no auth header
        Steps:
            1. Get the fence version.
            2. Run new/old version of DRS based on fence version.
            3. Get the drs signed url without header in response.
            4. Validate the expected response is recieved based on the fence version.
        """
        # The endpoint should return 401 if the version is >= 5.5.0 / 2021.10
        min_sem_ver = "3.2.0"
        min_monthly_release = "2023.04.0"
        monthly_release_cutoff = "2020"
        expected_response = 401

        # Get the fence version
        sem_ver_version = self.fence.get_version()

        # Verify which version to use
        if Version(sem_ver_version) >= Version(min_monthly_release) or (
            Version(sem_ver_version) < Version(monthly_release_cutoff)
            and Version(sem_ver_version) >= Version(min_sem_ver)
        ):
            logger.info(
                f"Running new version of DRS test b/c Fence version ({sem_ver_version}) is greater than 5.5.0/2021.10"
            )
        else:
            logger.info(
                f"Running old version of DRS test b/c Fence version ({sem_ver_version}) is less than 5.5.0/2021.10"
            )
            expected_response = 403

        # Get the drs signed url without header in request
        signed_url_res = self.drs.get_drs_signed_url_without_header(
            file=indexd_files["allowed"]
        )
        assert (
            signed_url_res.status_code == expected_response
        ), f"Expected status code {expected_response} but got {signed_url_res.status_code}"
