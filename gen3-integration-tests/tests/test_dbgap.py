"""
DBGAP
"""

import os
import uuid

import pytest
from cdislogging import get_logger
from services.fence import Fence
from services.indexd import Indexd

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
    "parentPhs001194File": {
        "file_name": "cascauth",
        "urls": [
            "s3://cdis-presigned-url-test/testdata",
            "gs://dcf-integration-test/file.txt",
        ],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad2"},
        "authz": ["/programs/phs001194"],
        "size": 11,
    },
    "childPhs000571File": {
        "file_name": "cascauth",
        "urls": [
            "s3://cdis-presigned-url-test/testdata",
            "gs://dcf-integration-test/file.txt",
        ],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad2"},
        "authz": ["/programs/phs000571"],
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
@pytest.mark.requires_google_bucket
class TestDbgap:
    indexd = Indexd()
    fence = Fence()
    variables = {}
    variables["created_indexd_dids"] = []
    variables["created_dbgap_dids"] = []

    @classmethod
    def setup_class(cls):
        # Removing test indexd records if they exist
        cls.indexd.delete_records(cls.variables["created_indexd_dids"])
        cls.indexd.delete_records(cls.variables["created_dbgap_dids"])

        # Adding indexd files
        for key, val in indexd_files.items():
            indexd_record = cls.indexd.create_records(records={key: val})
            cls.variables["created_indexd_dids"].append(indexd_record[0]["did"])

        # Delete SA Keys for user
        cls.fence.delete_google_sa_keys(user="main_account")

    @classmethod
    def teardown_class(cls):
        # Removing test indexd records
        cls.indexd.delete_records(cls.variables["created_indexd_dids"])
        cls.indexd.delete_records(cls.variables["created_dbgap_dids"])

    @pytest.mark.skip(
        reason="To avoid running usersync multiple times and since ONLY_DBGAP is not used in real time."
    )
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
            1. Run usersync job and add dbgap sync to yaml sync (done in test setup)
            2. Create S3 signed url. main_account has access to phs000178 through dbgap
            3. File should get downloaded. Verify the contents of the file.
        """
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
            self.indexd.create_records(records=new_dbgap_records, user="user2_account")
        except Exception as e:
            if "401" not in f"{e}":
                raise Exception(f"401 status code not returned. Exception : {e}")

        foo_bar_file_record = self.indexd.get_record(
            indexd_guid=new_dbgap_records["fooBarFile"]["did"]
        )
        assert (
            foo_bar_file_record is None
        ), f"Expected no record, but found {foo_bar_file_record}"

        # Create indexd record and retrieve record
        indexd_record = self.indexd.create_records(records=new_dbgap_records)
        self.variables["created_dbgap_dids"].append(indexd_record[0]["did"])
        foo_bar_file_record = self.indexd.get_record(
            indexd_guid=indexd_record[0]["did"], user="user2_account"
        )
        assert (
            "did" in foo_bar_file_record.keys()
        ), f"Expected did in record : {foo_bar_file_record}"

        # Update the record
        filename_change = {
            "file_name": "test_filename",
        }
        foo_bar_file_updated_record = self.indexd.update_record_via_api(
            guid=foo_bar_file_record["did"],
            rev=foo_bar_file_record["rev"],
            data=filename_change,
            user="user2_account",
        )
        assert (
            foo_bar_file_updated_record == 401
        ), f"Expected 401 status, but got {foo_bar_file_updated_record}"

        # Delete the record
        foo_bar_file_deleted_record = self.indexd.delete_record_via_api(
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
            self.indexd.create_records(records=new_dbgap_records, user="main_account")
        except Exception as e:
            if "401" not in f"{e}":
                raise Exception(f"401 status code not returned. Exception : {e}")

        foo_bar_file_record = self.indexd.get_record(
            indexd_guid=new_dbgap_records["fooBarFile"]["did"]
        )
        assert (
            foo_bar_file_record is None
        ), f"Expected no record, but found {foo_bar_file_record}"

        # Create indexd record and retrieve record
        indexd_record = self.indexd.create_records(records=new_dbgap_records)
        self.variables["created_dbgap_dids"].append(indexd_record[0]["did"])
        foo_bar_file_record = self.indexd.get_record(
            indexd_guid=indexd_record[0]["did"], user="main_account"
        )
        assert (
            "did" in foo_bar_file_record.keys()
        ), f"Expected did in record : {foo_bar_file_record}"

        # Update the record
        filename_change = {
            "file_name": "test_filename",
        }
        foo_bar_file_updated_record = self.indexd.update_record_via_api(
            guid=foo_bar_file_record["did"],
            rev=foo_bar_file_record["rev"],
            data=filename_change,
            user="main_account",
        )
        assert (
            foo_bar_file_updated_record == 401
        ), f"Expected 401 status, but got {foo_bar_file_updated_record}"

        # Delete the record
        foo_bar_file_deleted_record = self.indexd.delete_record_via_api(
            guid=foo_bar_file_record["did"],
            rev=foo_bar_file_record["rev"],
            user="main_account",
        )
        assert (
            foo_bar_file_deleted_record == 401
        ), f"Expected 401 status, but got {foo_bar_file_deleted_record}"

    def test_cascading_auth_create_signed_urls(self):
        """
        Scenario: dbGaP Sync: Cascading Auth - create signed urls from s3 and gs to download
        Steps:
            1. Create S3 signed url. main_account has access to phs001194 through dbgap
            2. Create S3 signed url. main_account has access to phs000571 through dbgap
        """
        # Create S3 signed url. main_account has access to phs001194 through dbgap
        phs001194_s3_signed_url = self.fence.create_signed_url(
            id=indexd_files["parentPhs001194File"]["did"],
            params=["protocol=s3"],
            user="main_account",
            expected_status=200,
        )
        phs001194_gs_signed_url = self.fence.create_signed_url(
            id=indexd_files["parentPhs001194File"]["did"],
            params=["protocol=gs"],
            user="main_account",
            expected_status=200,
        )

        phs001194_s3_file_contents = self.fence.get_file(phs001194_s3_signed_url["url"])
        phs001194_gs_file_contents = self.fence.get_file(phs001194_gs_signed_url["url"])
        assert (
            "Hi Zac!\ncdis-data-client uploaded this!\n" == phs001194_s3_file_contents
        ), f"Unable to get file contents. Response: {phs001194_s3_file_contents}"
        assert (
            "dcf-integration-test" == phs001194_gs_file_contents
        ), f"Unable to get file contents. Response: {phs001194_gs_file_contents}"

        # Create S3 signed url. main_account has access to phs000571 as its child of phs001194
        phs000571_s3_signed_url = self.fence.create_signed_url(
            id=indexd_files["childPhs000571File"]["did"],
            params=["protocol=s3"],
            user="main_account",
            expected_status=200,
        )
        phs000571_gs_signed_url = self.fence.create_signed_url(
            id=indexd_files["childPhs000571File"]["did"],
            params=["protocol=gs"],
            user="main_account",
            expected_status=200,
        )

        phs000571_s3_file_contents = self.fence.get_file(phs000571_s3_signed_url["url"])
        phs000571_gs_file_contents = self.fence.get_file(phs000571_gs_signed_url["url"])
        assert (
            "Hi Zac!\ncdis-data-client uploaded this!\n" == phs000571_s3_file_contents
        ), f"Unable to get file contents. Response: {phs000571_s3_file_contents}"
        assert (
            "dcf-integration-test" == phs000571_gs_file_contents
        ), f"Unable to get file contents. Response: {phs000571_gs_file_contents}"
