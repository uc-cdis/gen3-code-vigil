"""
DBGAP
"""

import os
import pytest
import uuid

from cdislogging import get_logger
from services.indexd import Indexd
from services.fence import Fence
from utils.gen3_admin_tasks import create_link_google_test_buckets, run_usersync_job

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


indexd_files = {
    "phs000178File": {
        "file_name": "testdata",
        "urls": [
            "s3://cdis-presigned-url-test/testdata",
            "gs://dcf-integration-test/file.txt",
        ],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "authz": ["/programs/phs000178"],
        "size": 9,
    },
    "phs000179File": {
        "file_name": "testdata",
        "urls": [
            "s3://cdis-presigned-url-test/testdata",
            "gs://dcf-integration-qa/file.txt",
        ],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad1"},
        "authz": ["/orgA/programs/phs000179"],
        "size": 10,
    },
    "anotherPhs000179File": {
        "file_name": "testdata",
        "urls": [
            "s3://cdis-presigned-url-test/testdata",
            "gs://dcf-integration-qa/file.txt",
        ],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad2"},
        "authz": ["/orgB/programs/phs000179"],
        "size": 11,
    },
    "QAFile": {
        "file_name": "testdata",
        "urls": [
            "s3://cdis-presigned-url-test/testdata",
            "gs://dcf-integration-qa/file.txt",
        ],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ac5"},
        "authz": ["/gen3/programs/QA/projects/foobar"],
        "size": 12,
    },
    "project12345File": {
        "file_name": "testdata",
        "size": 10,
        "hashes": {"md5": "e5c9a0d417f65226f564f438120381c5"},
        "urls": [
            "s3://cdis-presigned-url-test/testdata",
            "gs://dcf-integration-test/file.txt",
        ],
        "authz": ["/programs/PROJECT-12345"],
        "acl": ["PROJECT-12345"],
        "form": "object",
    },
}

new_dbgap_records = {
    "fooBarFile": {
        "file_name": "testdata",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad4"},
        "authz": ["/programs/phs000178"],
        "size": 13,
    },
}


@pytest.mark.indexd
@pytest.mark.fence
class TestDbgap:
    indexd = Indexd()
    fence = Fence()

    @classmethod
    def setup_class(cls):
        # Create and Link Google Test Buckets
        create_link_google_test_buckets(pytest.namespace)

        # Removing test indexd records if they exist
        cls.indexd.delete_file_indices(records=indexd_files)
        cls.indexd.delete_file_indices(records=new_dbgap_records)

        # Adding indexd files
        for key, val in indexd_files.items():
            indexd_record = cls.indexd.create_records(records={key: val})
            indexd_files[key]["did"] = indexd_record[0]["did"]
            indexd_files[key]["rev"] = indexd_record[0]["rev"]

        logger.info(indexd_files)

        # Run usersync job with "FORCE true ONLY_DBGAP true"
        # run_usersync_job(test_env_namespace=pytest.namespace, cmd="FORCE true ONLY_DBGAP true")

    @classmethod
    def teardown_setup(cls):
        # Removing test indexd records
        cls.indexd.delete_file_indices(records=indexd_files)
        cls.indexd.delete_file_indices(records=new_dbgap_records)

        # Run usersync job with "FORCE true ONLY_DBGAP true"
        run_usersync_job(test_env_namespace=pytest.namespace, cmd="FORCE true")

    def test_created_signed_urls_upload_urls(self):
        """
        Scenario: dbGaP Sync: created signed urls (from s3 and gs) to download, try creating urls to upload
        Steps:
            1. Create S3 signed url. main_account has access to phs000178 through dbgap
            2. Create S3 signed url. main_account doesn't have access to phs000179 through dbgap
            3. Get Upload presigned url from fence. Fence should not let main_account upload
        """
        # Create S3 signed url. main_account has access to phs000178 through dbgap
        phs000178_s3_signed_url = self.fence.create_signed_url(
            id=indexd_files["phs000178File"]["did"],
            params=["protocol=s3"],
            user="main_account",
            expected_status=200,
        )
        phs000178_gs_signed_url = self.fence.create_signed_url(
            id=indexd_files["phs000178File"]["did"],
            params=["protocol=gs"],
            user="main_account",
            expected_status=200,
        )

        phs000178_s3_file_contents = self.fence.get_file(phs000178_s3_signed_url["url"])
        phs000178_gs_file_contents = self.fence.get_file(phs000178_gs_signed_url["url"])
        assert (
            "Hi Zac!\ncdis-data-client uploaded this!\n" == phs000178_s3_file_contents
        ), f"Unable to get file contents. Response: {phs000178_s3_file_contents}"
        assert (
            "dcf-integration-test" == phs000178_gs_file_contents
        ), f"Unable to get file contents. Response: {phs000178_gs_file_contents}"

        # Create S3 signed url. main_account doesn't have access to phs000179 through dbgap
        phs000179_s3_signed_url = self.fence.create_signed_url(
            id=indexd_files["phs000179File"]["did"],
            params=["protocol=s3"],
            user="main_account",
            expected_status=401,
        )
        phs000179_gs_signed_url = self.fence.create_signed_url(
            id=indexd_files["phs000179File"]["did"],
            params=["protocol=gs"],
            user="main_account",
            expected_status=401,
        )
        another_phs000179_s3_signed_url = self.fence.create_signed_url(
            id=indexd_files["anotherPhs000179File"]["did"],
            params=["protocol=s3"],
            user="main_account",
            expected_status=401,
        )
        another_phs000179_gs_signed_url = self.fence.create_signed_url(
            id=indexd_files["anotherPhs000179File"]["did"],
            params=["protocol=gs"],
            user="main_account",
            expected_status=401,
        )

        assert (
            phs000179_s3_signed_url.status_code == 401
        ), f"Expected 401 status, but got {phs000179_s3_signed_url}"
        assert (
            phs000179_gs_signed_url.status_code == 401
        ), f"Expected 401 status, but got {phs000179_gs_signed_url}"
        assert (
            another_phs000179_s3_signed_url.status_code == 401
        ), f"Expected 401 status, but got {another_phs000179_s3_signed_url}"
        assert (
            another_phs000179_gs_signed_url.status_code == 401
        ), f"Expected 401 status, but got {another_phs000179_gs_signed_url}"

        # Get Upload presigned url from fence. Fence should not let main_account upload
        fence_upload_url = self.fence.get_url_for_data_upload_for_existing_file(
            guid=indexd_files["phs000178File"]["did"], user="main_account"
        )
        assert (
            fence_upload_url.status_code == 401
        ), f"Expected 401 status, but got {phs000178_s3_signed_url}"

    def test_ensure_combined_access(self):
        """
        Scenario: dbGaP + user.yaml Sync: ensure combined access
        Steps:
            1. Run usersync job and add dbgap sync to yaml sync
            2. Create S3 signed url. main_account has access to phs000178 through dbgap
            3. File should get downloaded. Verify the contents of the file.
        """
        # Run usersync job and add dbgap sync to yaml sync
        # Run usersync job with "FORCE true ADD_DBGAP true"
        run_usersync_job(
            test_env_namespace=pytest.namespace, cmd="ADD_DBGAP true FORCE true"
        )

        # Create S3 signed url. main_account has access to phs000178 through dbgap
        phs000178_s3_signed_url = self.fence.create_signed_url(
            id=indexd_files["phs000178File"]["did"],
            params=["protocol=s3"],
            user="main_account",
            expected_status=200,
        )
        qa_s3_signed_url = self.fence.create_signed_url(
            id=indexd_files["QAFile"]["did"],
            params=["protocol=s3"],
            user="main_account",
            expected_status=200,
        )

        # File should get downloaded. Verify the contents of the file.
        phs000178_s3_file_contents = self.fence.get_file(phs000178_s3_signed_url["url"])
        qa_s3_file_contents = self.fence.get_file(qa_s3_signed_url["url"])
        assert (
            "Hi Zac!\ncdis-data-client uploaded this!\n" == phs000178_s3_file_contents
        ), f"Unable to get file contents. Response: {phs000178_s3_file_contents}"
        assert (
            "Hi Zac!\ncdis-data-client uploaded this!\n" == qa_s3_file_contents
        ), f"Unable to get file contents. Response: {qa_s3_file_contents}"

    def test_user_without_dbgap_access_cannot_crud_indexd_records(self):
        """
        Scenario: dbGaP + user.yaml Sync (from prev test): ensure user without dbGap access cannot create/update/delete dbGaP indexd records
        Steps:
            1. Create indexd records using user2_account. No indexd record should be retrieved.
            2. Create indexd records using indexing_account. Expect record to be retrieved.
            3. user2_account doesn't have access to dbGap, so can't create/update/delete indexd record.
        """
        new_dbgap_records["fooBarFile"]["did"] = str(uuid.uuid4())
        # Indexd record creation should fail with user2_account
        try:
            self.indexd.create_records(files=new_dbgap_records, user="user2_account")
        except Exception as e:
            if "401" not in f"{e}":
                raise f"401 status code not returned. Exception : {e}"

        foo_bar_file_record = self.indexd.get_record(
            indexd_guid=new_dbgap_records["fooBarFile"]["did"]
        )
        assert (
            foo_bar_file_record is None
        ), f"Expected no record, but found {foo_bar_file_record}"

        # Create indexd record and retrieve record
        self.indexd.create_records(files=new_dbgap_records)
        foo_bar_file_record = self.indexd.get_record(
            indexd_guid=new_dbgap_records["fooBarFile"]["did"], user="user2_account"
        )
        assert (
            "did" in foo_bar_file_record.keys()
        ), f"Expected did in record : {foo_bar_file_record}"

        # Update the record
        filename_change = {
            "file_name": "test_filename",
        }
        foo_bar_file_updated_record = self.indexd.update_record(
            guid=foo_bar_file_record["did"],
            rev=foo_bar_file_record["rev"],
            data=filename_change,
            user="user2_account",
        )
        assert (
            foo_bar_file_updated_record == 401
        ), f"Expected 401 status, but got {foo_bar_file_updated_record}"

        # Delete the record
        foo_bar_file_deleted_record = self.indexd.delete_record(
            guid=foo_bar_file_record["did"],
            rev=foo_bar_file_record["rev"],
            user="user2_account",
        )
        assert (
            foo_bar_file_deleted_record == 401
        ), f"Expected 401 status, but got {foo_bar_file_deleted_record}"

    def test_user_with_dbgap_access_cannot_crud_indexd_records(self):
        """
        Scenario: dbGaP + user.yaml Sync (from prev test): ensure users with dbGap access cannot create/update/delete dbGaP indexd records
        Steps:
            1. Create indexd records using main_account. No indexd record should be retrieved.
            2. Create indexd records using indexing_account. Expect record to be retrieved.
            3. main_account has access to dbGap, but still can't create/update/delete indexd record.1.
        """
        new_dbgap_records["fooBarFile"]["did"] = str(uuid.uuid4())
        # Indexd record creation should fail with main_account
        try:
            self.indexd.create_records(files=new_dbgap_records, user="main_account")
        except Exception as e:
            if "401" not in f"{e}":
                raise f"401 status code not returned. Exception : {e}"

        foo_bar_file_record = self.indexd.get_record(
            indexd_guid=new_dbgap_records["fooBarFile"]["did"]
        )
        assert (
            foo_bar_file_record is None
        ), f"Expected no record, but found {foo_bar_file_record}"

        # Create indexd record and retrieve record
        self.indexd.create_records(files=new_dbgap_records)
        foo_bar_file_record = self.indexd.get_record(
            indexd_guid=new_dbgap_records["fooBarFile"]["did"], user="main_account"
        )
        assert (
            "did" in foo_bar_file_record.keys()
        ), f"Expected did in record : {foo_bar_file_record}"

        # Update the record
        filename_change = {
            "file_name": "test_filename",
        }
        foo_bar_file_updated_record = self.indexd.update_record(
            guid=foo_bar_file_record["did"],
            rev=foo_bar_file_record["rev"],
            data=filename_change,
            user="main_account",
        )
        assert (
            foo_bar_file_updated_record == 401
        ), f"Expected 401 status, but got {foo_bar_file_updated_record}"

        # Delete the record
        foo_bar_file_deleted_record = self.indexd.delete_record(
            guid=foo_bar_file_record["did"],
            rev=foo_bar_file_record["rev"],
            user="main_account",
        )
        assert (
            foo_bar_file_deleted_record == 401
        ), f"Expected 401 status, but got {foo_bar_file_deleted_record}"
