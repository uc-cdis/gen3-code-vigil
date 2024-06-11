"""
PRESIGNED URL
"""

import os
import pytest

from services.indexd import Indexd
from services.fence import Fence

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.indexd
@pytest.mark.fence
class TestPresignedURL:
    indexd = Indexd()

    @classmethod
    def setup_class(cls):
        files = {
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
        }
        logger.info("Creating Indexd Records")
        cls.indexd_records = cls.indexd.create_files(files=files)

    @classmethod
    def teardown_class(cls):
        indexd = Indexd()
        logger.info("Deleting Indexd Records")
        for record in cls.indexd_records:
            rev = indexd.get_rev(record)
            indexd.delete_record(guid=record["did"], rev=rev)

    def get_indexd_record(cls, filename):
        for record in cls.indexd_records:
            if (
                cls.indexd.get_record(indexd_guid=record["did"])["file_name"]
                == filename
            ):
                return record
        logger.error(f"No indexd record found for filename: {filename}")
        raise

    def test_get_presigned_url(cls):
        """
        Scenario: Get presigned-url
        Steps:
            1. Create indexd record using allowed key information in files as setup
            2. Create a signed url using did from step 1.
            3. Validate the singed url response has a url defined
            4. Validate the contents of the file are as expected
        """
        fence = Fence()
        indexd_record = cls.get_indexd_record(filename="test_valid")
        signed_url_res = fence.createSignedUrl(
            id=indexd_record["did"], user="main_account", expectedStatus=200
        )
        fence.check_file_equals(
            signed_url_res, "Hi Zac!\ncdis-data-client uploaded this!\n"
        )
        return

    def test_get_presigned_url_user_doesnot_have_permission(cls):
        """
        Scenario: Get presigned-url user doesn't have permission
        Steps:
            1. Create indexd record using not_allowed key information in files as setup
            2. Create a signed url using did from step 1.
            3. Verify the fence error is 'You don\'t have access permission on this file'
        """
        fence = Fence()
        indexd_record = cls.get_indexd_record(filename="test_not_allowed")
        signed_url_res = fence.createSignedUrl(
            id=indexd_record["did"], user="main_account", expectedStatus=401
        )
        msg = "You don&#39;t have access permission on this file"
        if msg not in signed_url_res.content.decode():
            logger.error(f"{msg} not found")
            logger.error(signed_url_res.content.decode())
            raise

    def test_get_presigned_url_with_invalid_protocol(cls):
        """
        Scenario: Get presigned-url with invalid protocol
        Steps:
            1. Create indexd record using invalid_protocol key information in files as setup
            2. Create a signed url using did from step 1 and protocol as s2.
            3. Verify the fence error is 'The specified protocol s2 is not supported'
        """
        fence = Fence()
        indexd_record = cls.get_indexd_record(filename="test_invalid_protocol")
        signed_url_res = fence.createSignedUrl(
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

    def test_get_presigned_url_with_protocol_not_available(cls):
        """
        Scenario: Get presigned-url with protocol not available in indexd document
        Steps:
            1. Create indexd record using allowed key information in files as setup
            2. Create a signed url using did from step 1 and protocol as s2.
            3. Verify the fence error is 'File {did} does not have a location with specified protocol s2.'
        """
        fence = Fence()
        indexd_record = cls.get_indexd_record(filename="test_valid")
        signed_url_res = fence.createSignedUrl(
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

    def test_get_presigned_url_with_protocol_not_exist_for_file(cls):
        """
        Scenario: Get presigned-url with protocol not exist for file
        Steps:
            1. Create indexd record using http_link key information in files as setup
            2. Create a signed url using did from step 1 and protocol as s3.
            3. Verify the fence error is 'File {did} does not have a location with specified protocol s3.'
        """
        fence = Fence()
        indexd_record = cls.get_indexd_record(filename="test_protocol")
        signed_url_res = fence.createSignedUrl(
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

    def test_get_presigned_url_no_data(cls):
        """
        Scenario: Get presigned-url no data
        Steps:
            1. Create indexd record using no_link key information in files as setup
            2. Create a signed url using did from step 1 and protocol as s3.
            3. Verify the fence error is 'File {did} does not have a location with specified protocol s3.'
        """
        fence = Fence()
        indexd_record = cls.get_indexd_record(filename="test_no_link")
        signed_url_res = fence.createSignedUrl(
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

    def test_get_presigned_url_no_requested_protocol_no_data(cls):
        """
        Scenario: Get presigned-url no requested protocol, no data
        Steps:
            1. Create indexd record using no_link key information in files as setup
            2. Create a signed url using did from step 1.
            3. Verify the fence error is 'Can\'t find any file locations.'
        """
        fence = Fence()
        indexd_record = cls.get_indexd_record(filename="test_no_link")
        signed_url_res = fence.createSignedUrl(
            id=indexd_record["did"], user="main_account", expectedStatus=404
        )
        msg = "Can&#39;t find any file locations."
        if msg not in signed_url_res.content.decode():
            logger.error(f"{msg} not found")
            logger.error(signed_url_res.content.decode())
            raise
