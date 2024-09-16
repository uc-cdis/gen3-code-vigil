import pytest

from pages.login import LoginPage
from services.fence import Fence
from services.indexd import Indexd
from utils import logger
from utils import TEST_DATA_PATH_OBJECT
from gen3.auth import Gen3Auth
from gen3.file import Gen3File


from playwright.sync_api import Page


@pytest.mark.fence
class TestGoogleDataAccess:
    fence = Fence()
    login_page = LoginPage()
    indexd = Indexd()
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
            1. Link google account for user dcf-integration-test-0
            2. Create temporary google credentials
            3. Create presigned urls for QA and Test indexd files
            4. Verify QA file is accessible with 200 status code and Test file is inaccessible with 401 code
               User dcf-integration-test-0 has access to QA and not Test project.
        """
        # Login from UI to get access_token
        self.login_page.go_to(page)
        token = self.login_page.login(page, user="user0_account")["value"]

        # Delete previous temp Google Credentials
        self.fence.delete_previous_google_service_account_keys(access_token=token)

        # Unlinking Google Account for user0
        unlinking_status_code = self.fence.unlink_google_account(user="user0_account")
        assert unlinking_status_code in (
            200,
            404,
        ), f"Expected Google account to be unlinked, but got status_code {unlinking_status_code}"

        # Linking Google Account for user0
        linking_url, linking_status_code = self.fence.link_google_account(
            user="user0_account"
        )
        assert (
            linking_status_code == 200
        ), f"Expected Google account to be linked, but got status_code {linking_status_code}"

        # Creating Temporary Google Credentials
        temp_creds_json, status_code = self.fence.create_temp_google_creds(
            user="user0_account", access_token=token, expires_in=300
        )
        assert (
            status_code == 200
        ), f"Expected Google credentials to be created but got status {status_code}"

        # Creating Presigned URLs for QA and Test
        # auth = Gen3Auth(refresh_token=pytest.api_keys["user0_account"], endpoint=f"{pytest.root_url}")
        # file = Gen3File(auth)
        # qa_presigned_url = file.get_presigned_url(guid=self.indexd_files["qa_file"]["did"], protocol='gs')
        qa_presigned_url = self.fence.create_signed_url(
            id=self.indexd_files["qa_file"]["did"],
            params=["protocol=gs"],
            user="user0_account",
            expected_status=200,
        )
        test_presigned_url = self.fence.create_signed_url(
            id=self.indexd_files["test_file"]["did"],
            params=["protocol=gs"],
            user="user0_account",
            expected_status=401,
        )

        # Verify the contents of /abc signed url
        # logger.info(qa_presigned_url)
        # self.fence.check_file_equals(qa_presigned_url, "dcf-integration-qa")

        key_path_file = (
            TEST_DATA_PATH_OBJECT
            / "google_creds"
            / f"{temp_creds_json['private_key_id']}.json"
        )

        logger.info(
            self.fence.read_file_from_google_storage(
                bucket_name="dcf-integration-qa",
                file_name="file.txt",
                key_path_file=key_path_file,
            )
        )
        logger.info(
            self.fence.read_file_from_google_storage(
                bucket_name="dcf-integration-test",
                file_name="file.txt",
                key_path_file=key_path_file,
            )
        )
