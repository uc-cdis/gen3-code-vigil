import pytest
from pages.login import LoginPage
from playwright.sync_api import Page
from services.fence import Fence
from services.indexd import Indexd
from utils import logger


@pytest.mark.skipif(
    "fence" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.fence
@pytest.mark.requires_google_bucket
class TestGoogleDataAccess:
    fence = Fence()
    login_page = LoginPage()
    indexd = Indexd()
    page = Page
    variables = {}
    variables["indexd_record_dids"] = []
    indexd_files = {
        "qa_file": {
            "file_name": "file.txt",
            "hashes": {"md5": "9573c8ad851c0a150d78ff4755b97920"},
            "size": 18,
            "acl": ["QA"],
            "urls": ["gs://dcf-integration-qa/file.txt"],
        },
        "test_file": {
            "file_name": "file.txt",
            "hashes": {"md5": "17bc0fb10a1c8df6940cdf7127042dd7"},
            "size": 20,
            "acl": ["test"],
            "urls": ["gs://dcf-integration-test/file.txt"],
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

    def test_google_data_access(self, page: Page):
        """
        Scenario: Google Data Access dcf-integration-test-0
        Steps:
            1. Create presigned urls for QA and Test indexd files
            2. Verify QA file is accessible with 200 status code and Test file is inaccessible with 401 code
               User dcf-integration-test-0 has access to QA and not Test project.
        Note : Make sure to run the fence-create google bucket command and perform usersync to setup access for
               google buckets.
        """
        # Delete SA keys from Google
        self.fence.delete_google_sa_keys(page=page, user="user0_account")
        qa_presigned_url = self.fence.create_signed_url(
            id=self.indexd_files["qa_file"]["did"],
            params=["protocol=gs"],
            user="user0_account",
            expected_status=200,
        )

        # Verify the contents of qa_presigned_url
        self.fence.check_file_equals(qa_presigned_url, "dcf-integration-qa")

        test_presigned_url = self.fence.create_signed_url(
            id=self.indexd_files["test_file"]["did"],
            params=["protocol=gs"],
            user="user0_account",
            expected_status=401,
        )
