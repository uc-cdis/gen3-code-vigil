"""
RAS Passports
"""

import os

import pytest
import requests
from cdislogging import get_logger
from pages.login import LoginPage
from playwright.sync_api import Page
from services.drs import Drs
from services.fence import Fence
from services.indexd import Indexd
from services.ras import RAS

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "error"))

indexd_files = {
    "test_with_ras_permission": {
        "acl": [],
        "authz": ["/programs/phs000000.c11"],
        "file_name": "ras_passport_test_file",
        "hashes": {"md5": "587efb5d96f695710a8df9c0dbb96eb0"},
        "size": 15,
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
    "indexd" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.indexd
@pytest.mark.fence
@pytest.mark.ras
class TestRasPassport:
    @classmethod
    def setup_class(cls):
        cls.BASE_URL = pytest.root_url
        cls.USER_ENDPOINT = "/user/user"
        cls.login_page = LoginPage()
        cls.indexd = Indexd()
        cls.fence = Fence()
        cls.drs = Drs()
        cls.ras = RAS()
        cls.variables = {}
        cls.variables["created_indexd_dids"] = []
        cls.env_vars = [
            "CI_TEST_RAS_USERNAME",
            "CI_TEST_RAS_PASSWORD",
        ]
        # Validate creds required for test that are defined as env variable
        cls.ras.validate_creds(test_creds=cls.env_vars)

        # Adding file to IndexD
        for key, val in indexd_files.items():
            indexd_record = cls.indexd.create_records(records={key: val})
            cls.variables["created_indexd_dids"].append(indexd_record[0]["did"])

    @classmethod
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
        client_id = pytest.clients["ras-test-client"]["client_id"]
        client_secret = pytest.clients["ras-test-client"]["client_secret"]
        scope = "openid profile email ga4gh_passport_v1 researcher_role"
        username = os.environ["CI_TEST_RAS_USERNAME"]
        password = os.environ["CI_TEST_RAS_PASSWORD"]
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
        if access_token:
            user_info_response = requests.get(
                f"{self.BASE_URL}{self.USER_ENDPOINT}",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"bearer {access_token}",
                },
            )

    def test_get_drs_presigned_url(self):
        """
        Scenario: get drs presigned-url
        Steps:
            1. Get the drs presigned url for the created ras indexd record
            2. Validate the content of the file.
        """
        signed_url_res = self.drs.get_drs_signed_url(
            file=indexd_files["test_with_ras_permission"]
        )
        logger.error("SIGNED URL CONTENT: %s", signed_url_res.content)
        logger.error("SIGNED URL Code: %s", signed_url_res.status_code)
        self.fence.check_file_equals(
            signed_url_res=signed_url_res.json(),
            file_content="Hi Zac!\ncdis-data-client uploaded this!\n",
        )
