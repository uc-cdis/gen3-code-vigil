"""
PRESIGNED URL
"""

import os
import pytest

from services.indexd import Indexd
from services.fence import Fence

from cdislogging import get_logger

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
        "filename": "test_protocol",
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
    "clever_safe_test_file1": {
        "filename": "test",
        "link": "s3://fence-cleversafe-test/test",
        "md5": "d8e8fca2dc0f896fd7cb4cb0031ba249",
        "acl": ["QA"],
        "size": 5,
    },
}


@pytest.mark.indexd
@pytest.mark.fence
class TestPresignedURL:
    indexd = Indexd()
    fence = Fence()

    @classmethod
    def setup_class(cls):
        # Removing test indexd records if they exist
        cls.indexd.delete_file_indices(records=indexd_files)

        logger.info("Creating Indexd Records")
        # Adding indexd files used to test signed urls
        for key, val in indexd_files.items():
            indexd_record = cls.indexd.create_files(files={key: val})
            indexd_files[key]["did"] = indexd_record[0]["did"]
            indexd_files[key]["rev"] = indexd_record[0]["rev"]

    @classmethod
    def teardown_class(cls):
        logger.info("Deleting Indexd Records")
        cls.indexd.delete_file_indices(records=indexd_files)

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
            id=indexd_record["did"], user="main_account", expectedStatus=200
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
            id=indexd_record["did"], user="main_account", expectedStatus=401
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
            expectedStatus=400,
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
            expectedStatus=404,
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
            expectedStatus=404,
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
            expectedStatus=404,
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
            id=indexd_record["did"], user="main_account", expectedStatus=404
        )
        msg = "Can&#39;t find any file locations."
        if msg not in signed_url_res.content.decode():
            logger.error(f"{msg} not found")
            logger.error(signed_url_res.content.decode())
            raise

    @pytest.mark.clever_safe
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
        signed_url_res = self.fence.create_signed_url(
            id=indexd_files["clever_safe_test_file1"]["did"],
            user="main_account",
            expectedStatus=200,
        )

        # Verify signed url is created
        assert (
            "url" in signed_url_res.keys()
        ), "Could not find url keyword in signed url"

        # Verify the contents of file downloaded using signed url
        self.fence.check_file_equals(signed_url_res, "test\n")
