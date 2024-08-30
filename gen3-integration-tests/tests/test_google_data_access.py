import pytest

from utils import logger
from services.fence import Fence
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from services.indexd import Indexd


@pytest.mark.fence
@pytest.mark.serial
class TestGoogleDataAccess:
    fence = Fence()
    indexd = Indexd()
    variables = {}
    variables["indexd_record_dids"] = []
    indexd_files = {
        "qa_file": {
            "file_name": "file.txt",
            "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
            "size": 9,
            "acl": ["QA"],
            "url": ["gs://dcf-integration-qa/file.txt"],
        },
        "test_file": {
            "file_name": "file.txt",
            "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
            "size": 10,
            "acl": ["test"],
            "url": ["gs://dcf-integration-test/file.txt"],
        },
    }

    @classmethod
    def setup_class(cls):
        # Creating indexd records for the test
        for key, val in cls.indexd_files.items():
            indexd_record = cls.indexd.create_records(records={key: val})
            cls.variables["indexd_record_dids"].append(indexd_record[0]["did"])

    @classmethod
    def teardown_class(cls):
        # Deleting indexd records
        cls.indexd.delete_records(cls.variables["indexd_record_dids"])

    def test_google_data_access(self):
        """
        Scenario: Google Data Access dcf-integration-test-0
        Steps:
            1.
        """
        # Unlinking Google Account for user0
        unlinking_status_code = self.fence.unlink_google_account(user="user0_account")
        assert (
            unlinking_status_code == 200
        ), f"Expected Google account to be unlinked, but got status_code {linking_status_code}"

        # Linking Google Account for user0
        linking_url, linking_status_code = self.fence.link_google_account(
            user="user0_account"
        )
        assert (
            linking_status_code == 200
        ), f"Expected Google account to be linked, but got status_code {linking_status_code}"

        # Creating Temporary Google Credentials
        temp_creds_json, status_code = self.fence.create_temp_google_creds(
            user="user0_account"
        )
        assert status_code == 200, f"Expected Google credentials to be created"

        # Creating Presigned URLs for QA and Test
        qa_presigned_url = self.fence.create_signed_url(
            id=self.indexd_files["qa_file"]["did"],
            params=["protocol=s3"],
            user="user2_account",
            expected_status=200,
        )
        test_presigned_url = self.fence.create_signed_url(
            id=self.indexd_files["test_file"]["did"],
            params=["protocol=s3"],
            user="user2_account",
            expected_status=200,
        )
