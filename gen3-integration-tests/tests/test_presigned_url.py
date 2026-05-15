"""
PRESIGNED URL
"""

import os

import pytest
from cdislogging import get_logger
from services.fence import Fence
from services.indexd import Indexd

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


indexd_files = {
    "allowed": {
        "file_name": "test_valid",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["jenkins"],
        "size": 9,
    },
    "allowed2": {
        "file_name": "test_valid",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["jenkins"],
        "size": 9,
    },
    "allowed_authz": {
        "file_name": "test_valid",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["jenkins"],
        "authz": ["/programs/jenkins"],
        "size": 9,
    },
    "not_allowed": {
        "file_name": "test_not_allowed",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["acct"],
        "size": 9,
    },
    "no_link": {
        "file_name": "test_no_link",
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["jenkins"],
        "size": 9,
    },
    "http_link": {
        "file_name": "test_protocol",
        "urls": ["http://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["jenkins"],
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


@pytest.mark.skipif(
    "fence" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.skipif(
    "indexd" not in pytest.deployed_services,
    reason="indexd service is not running on this environment",
)
@pytest.mark.indexd
@pytest.mark.fence
@pytest.mark.gen3sdk
class TestPresignedURL:
    @classmethod
    def setup_class(cls):
        cls.indexd = Indexd()
        cls.fence = Fence()
        cls.variables = {}
        cls.variables["created_indexd_dids"] = []
        logger.info("Creating Indexd Records")
        # Adding indexd files used to test signed urls
        for key, val in indexd_files.items():
            indexd_record = cls.indexd.create_records(records={key: val})
            cls.variables["created_indexd_dids"].append(indexd_record[0]["did"])

    @classmethod
    def teardown_class(cls):
        logger.info("Deleting Indexd Records")
        cls.indexd.delete_records(guids=cls.variables["created_indexd_dids"])

    def get_indexd_record(cls, filename):
        for record in cls.indexd_records:
            if (
                cls.indexd.get_record(indexd_guid=record["did"])["file_name"]
                == filename
            ):
                return record
        logger.error(f"No indexd record found for filename: {filename}")
        raise

    def test_get_presigned_url(self):
        """
        Scenario: Get presigned-url
        Steps:
            1. Create indexd record using allowed key information in files as setup
            2. Create a signed url using did from step 1.
            3. Validate the singed url response has a url defined
            4. Validate the contents of the file are as expected
        """
        indexd_record = indexd_files["allowed"]
        signed_url_res = self.fence.create_signed_url(
            id=indexd_record["did"], user="main_account", expected_status=200
        )
        self.fence.check_file_equals(
            signed_url_res, "Hi Zac!\ncdis-data-client uploaded this!\n"
        )
        return

    def test_get_presigned_url_user_doesnot_have_permission(self):
        """
        Scenario: Get presigned-url user doesn't have permission
        Steps:
            1. Create indexd record using not_allowed key information in files as setup
            2. Create a signed url using did from step 1.
            3. Verify the fence error is 'You don\'t have access permission on this file'
        """
        indexd_record = indexd_files["not_allowed"]
        signed_url_res = self.fence.create_signed_url(
            id=indexd_record["did"], user="main_account", expected_status=401
        )
        msg = "You don&#39;t have access permission on this file"
        if msg not in signed_url_res.content.decode():
            logger.error(f"{msg} not found")
            logger.error(signed_url_res.content.decode())
            raise

    def test_get_presigned_url_with_invalid_protocol(self):
        """
        Scenario: Get presigned-url with invalid protocol
        Steps:
            1. Create indexd record using invalid_protocol key information in files as setup
            2. Create a signed url using did from step 1 and protocol as s2.
            3. Verify the fence error is 'The specified protocol s2 is not supported'
        """
        indexd_record = indexd_files["invalid_protocol"]
        signed_url_res = self.fence.create_signed_url(
            id=indexd_record["did"],
            user="main_account",
            expected_status=400,
            params=["protocol=s2"],
        )
        msg = "The specified protocol s2 is not supported"
        if msg not in signed_url_res.content.decode():
            logger.error(f"{msg} not found")
            logger.error(signed_url_res.content.decode())
            raise

    def test_get_presigned_url_with_protocol_not_available(self):
        """
        Scenario: Get presigned-url with protocol not available in indexd document
        Steps:
            1. Create indexd record using allowed key information in files as setup
            2. Create a signed url using did from step 1 and protocol as s2.
            3. Verify the fence error is 'File {did} does not have a location with specified protocol s2.'
        """
        indexd_record = indexd_files["allowed"]
        signed_url_res = self.fence.create_signed_url(
            id=indexd_record["did"],
            user="main_account",
            expected_status=404,
            params=["protocol=s2"],
        )
        msg = f"File {indexd_record['did']} does not have a location with specified protocol s2."
        if msg not in signed_url_res.content.decode():
            logger.error(f"{msg} not found")
            logger.error(signed_url_res.content.decode())
            raise

    def test_get_presigned_url_with_protocol_not_exist_for_file(self):
        """
        Scenario: Get presigned-url with protocol not exist for file
        Steps:
            1. Create indexd record using http_link key information in files as setup
            2. Create a signed url using did from step 1 and protocol as s3.
            3. Verify the fence error is 'File {did} does not have a location with specified protocol s3.'
        """
        indexd_record = indexd_files["http_link"]
        signed_url_res = self.fence.create_signed_url(
            id=indexd_record["did"],
            user="main_account",
            expected_status=404,
            params=["protocol=s3"],
        )
        msg = f"File {indexd_record['did']} does not have a location with specified protocol s3."
        if msg not in signed_url_res.content.decode():
            logger.error(f"{msg} not found")
            logger.error(signed_url_res.content.decode())
            raise

    def test_get_presigned_url_no_data(self):
        """
        Scenario: Get presigned-url no data
        Steps:
            1. Create indexd record using no_link key information in files as setup
            2. Create a signed url using did from step 1 and protocol as s3.
            3. Verify the fence error is 'File {did} does not have a location with specified protocol s3.'
        """
        indexd_record = indexd_files["no_link"]
        signed_url_res = self.fence.create_signed_url(
            id=indexd_record["did"],
            user="main_account",
            expected_status=404,
            params=["protocol=s3"],
        )
        msg = f"File {indexd_record['did']} does not have a location with specified protocol s3."
        if msg not in signed_url_res.content.decode():
            logger.error(f"{msg} not found")
            logger.error(signed_url_res.content.decode())
            raise

    def test_get_presigned_url_no_requested_protocol_no_data(self):
        """
        Scenario: Get presigned-url no requested protocol, no data
        Steps:
            1. Create indexd record using no_link key information in files as setup
            2. Create a signed url using did from step 1.
            3. Verify the fence error is 'Can\'t find any file locations.'
        """
        indexd_record = indexd_files["no_link"]
        signed_url_res = self.fence.create_signed_url(
            id=indexd_record["did"], user="main_account", expected_status=404
        )
        msg = "Can&#39;t find any file locations."
        if msg not in signed_url_res.content.decode():
            logger.error(f"{msg} not found")
            logger.error(signed_url_res.content.decode())
            raise

    def test_get_bulk_presigned_urls(self):
        """
        Scenario: Get bulk presigned-urls
        Steps:
            1. Use multiple indexd records created in setup
            2. Request bulk signed urls
            3. Validate urls are returned for each GUID
            4. Validate file contents match expected values
        """
        allowed_record = indexd_files["allowed"]
        allowed_record2 = indexd_files["allowed2"]
        not_allowed_record = indexd_files["not_allowed"]
        allowed_authz_record = indexd_files["allowed_authz"]

        guids = [
            allowed_record["did"],
            allowed_record2["did"],
            allowed_authz_record["did"],
            not_allowed_record["did"],
        ]

        res = self.fence.create_bulk_signed_urls(
            guids=guids,
            user="main_account",
            expected_status=200,
        )

        assert "urls" in res, f"'urls' missing in response: {res}"
        assert "failed_file_ids" in res, f"'failed_file_ids' missing in response: {res}"

        dids = []
        signed_url_res = None
        for drs_obj in res.get("urls"):
            dids.append(drs_obj["drs_object_id"])
            if drs_obj["drs_object_id"] == allowed_record["did"]:
                signed_url_res = {"url": drs_obj["url"]}
        # Validate success case
        assert allowed_record["did"] in dids, "Allowed GUID missing from urls"
        assert allowed_record2["did"] in dids, "Allowed GUID missing from urls"
        assert (
            allowed_authz_record["did"] in dids
        ), "Allowed with authz GUID missing from urls"

        self.fence.check_file_equals(
            signed_url_res, "Hi Zac!\ncdis-data-client uploaded this!\n"
        )

        failed_ids = []
        for failure in res.get("failed_file_ids"):
            for id in failure.get("object_ids", []):
                failed_ids.append(id)

        # Validate failure case
        assert (
            not_allowed_record["did"] in failed_ids
        ), "Unauthorized GUID should be in failed_file_ids"
