"""
RAS Passports Parse Check.
1. Create an indexd record with an authz for one of the permissions in the passport
2. Call the user/user endpoint to see that the passport is parsed correctly
3. Finally, get the presigned URL to download the file.
"""

import os

import pytest
import requests
from pages.login import LoginPage
from playwright.sync_api import Page
from services.drs import Drs
from services.fence import Fence
from services.indexd import Indexd
from services.ras import RAS
from utils import logger

indexd_files = {
    "test_with_ras_permission": {
        "authz": ["/programs/phs000000.c11"],
        "file_name": "ras_passport_test_file",
        "hashes": {
            "md5": "73d643ec3f4beb9020eef0beed440ad0"
        },  # pragma: allowlist secret
        "size": 9,
        "urls": [
            "s3://cdis-presigned-url-test/testdata",
            "gs://cdis-presigned-url-test/testdata",
        ],
    },
}


@pytest.mark.skipif(
    "nightly-build" not in pytest.hostname,
    reason="Test is being run for ras auth which is only on nightly-build namespaces",
)
@pytest.mark.skipif(
    "fence" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.skipif(
    "indexd" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.frontend
@pytest.mark.indexd
@pytest.mark.fence
@pytest.mark.ras
@pytest.mark.requires_fence_client
class TestRasPassport:
    @classmethod
    def setup_class(cls):
        cls.BASE_URL = pytest.root_url
        cls.USER_ENDPOINT = "/user/user"
        cls.fence = Fence()
        cls.drs = Drs()
        cls.ras = RAS()
        cls.indexd = Indexd()
        cls.variables = {}
        cls.variables["created_indexd_dids"] = []
        cls.login_page = LoginPage()
        cls.env_vars = [
            "RAS_IAL2_USERID",
            "RAS_IAL2_PASSWORD",
            "CI_TEST_RAS_EMAIL",
            "CI_TEST_RAS_PASSWORD",
        ]
        # Validate creds required for test that are defined as env variable
        cls.ras.validate_creds(test_creds=cls.env_vars)

        # Adding file to IndexD
        for key, val in indexd_files.items():
            indexd_record = cls.indexd.create_records(records={key: val})
            cls.variables["created_indexd_dids"].append(indexd_record[0]["did"])

    # @classmethod
    def teardown_class(cls):
        # Deleting indexd records
        cls.indexd.delete_records(cls.variables["created_indexd_dids"])

    def test_ras_passport_is_parsed(self, page: Page):
        """
        Scenario: Ensure the RAS Passport is parsed correctly for a IAL2 RAS User on login.
        Steps:
            1. Get client_id and client_secret for RAS User
            2. Use client_id and client_secret, get auth_code and tokens with OIDC bootstrapping
            3. With access_token, check the /user/user endpoint to have ga4gh_passport_v1 parsed with 600
               consent codes in it.
        """
        client_id = pytest.clients["ras-test-ial2"]["client_id"]
        client_secret = pytest.clients["ras-test-ial2"]["client_secret"]
        scope = "openid user data ga4gh_passport_v1"
        username = os.environ["RAS_IAL2_USERID"]
        password = os.environ["RAS_IAL2_PASSWORD"]
        email = "burtonk@uchicago.edu"

        token = self.ras.get_tokens(
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
            username=username,
            password=password,
            page=page,
            email=email,
        )
        assert (
            "access_token" in token
        ), "access_token is missing from the refresh_token response."
        access_token = token.get("access_token")

        # Call the user/user endpoint to see if passport has been parsed.
        if access_token:
            user_info_response = self.fence.get_user_info(access_token=access_token)
            resources = user_info_response["resources"]
            phs_resources = [r for r in resources if r.startswith("/programs/phs")]
            # Assert there are 600 or so phs studies.
            assert (
                len(phs_resources) >= 600
            ), f"Expected at least 600 phs resources, found {len(phs_resources)}"

    @pytest.mark.gen3sdk
    def test_get_drs_presigned_url(self, page: Page):
        """
        Scenario: Get drs presigned-url and download a file
        Steps:
            1. Login with user RAS_IAL2_USERID
            2. Get the drs presigned url for the created ras indexd record
            3. Validate the content of the file downloaded.
        """
        login_page = LoginPage()
        login_page.go_to(page)
        login_page.ras_login(
            page,
            username=os.getenv("RAS_IAL2_USERID"),
            password=os.getenv("RAS_IAL2_PASSWORD"),
            email="burtonk@uchicago.edu",
        )
        access_token_cookie = next(
            (
                cookie
                for cookie in page.context.cookies()
                if cookie["name"] == "access_token"
            ),
            None,
        )
        access_token = access_token_cookie["value"]
        logger.info(access_token)
        response, status_code = self.drs.get_drs_signed_url_using_gen3sdk(
            file=indexd_files["test_with_ras_permission"],
            access_token=access_token,
        )
        assert (
            status_code == 200
        ), f"Expected status_code to be 200 but got {status_code}"
        file_content = "Hi Zac!\ncdis-data-client uploaded this!\n"
        contents = self.fence.get_file(response)
        assert (
            contents == file_content
        ), f"Data don't match.\n{contents}\n{file_content}"
        # Perform Logout
        login_page.logout(page)

    @pytest.mark.gen3sdk
    def test_failed_get_drs_presigned_url(self, page: Page):
        """
        Scenario: Pre-signed url fails for RAS user without access
        Steps:
            1. 1. Login with user CI_TEST_RAS_EMAIL
            2. Get the drs presigned url for the created ras indexd record
            3. Validate the presigned url is not created as user doesn't have permission
        """
        login_page = LoginPage()
        login_page.go_to(page)
        login_page.ras_login(
            page,
        )
        access_token_cookie = next(
            (
                cookie
                for cookie in page.context.cookies()
                if cookie["name"] == "access_token"
            ),
            None,
        )
        access_token = access_token_cookie["value"]
        logger.info(access_token)
        response, status_code = self.drs.get_drs_signed_url_using_gen3sdk(
            file=indexd_files["test_with_ras_permission"],
            access_token=access_token,
        )
        assert (
            status_code == 401
        ), f"Expected status_code to be 401 but got {status_code}"
        login_page.logout(page)
