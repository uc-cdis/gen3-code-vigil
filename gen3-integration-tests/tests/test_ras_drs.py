"""
RAS DRS
"""

import os
import time

import pytest
import requests
from cdislogging import get_logger
from playwright.sync_api import Page
from services.fence import Fence
from services.indexd import Indexd
from services.ras import RAS

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))

indexd_files = {
    "Permission_test_user_should_have": {
        "acl": [],
        "authz": ["/programs/phs002409.c1"],
        "file_name": "ras_test_file",
        "hashes": {"md5": "587efb5d96f695710a8df9c0dbb96eb0"},
        "size": 15,
        "urls": [
            "s3://cdis-presigned-url-test/testdata",
            "gs://cdis-presigned-url-test/testdata",
        ],
    },
    "Permission_test_user_should_not_have": {
        "acl": [],
        "authz": ["/programs/phs002410.c1"],
        "file_name": "ras_test_file",
        "hashes": {"md5": "587efb5d96f695710a8df9c0dbb96eb0"},
        "size": 15,
        "urls": [
            "s3://cdis-presigned-url-test/testdata",
            "gs://cdis-presigned-url-test/testdata",
        ],
    },
}


@pytest.mark.skipif(
    "indexd" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.skipif(
    "indexd" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.indexd
@pytest.mark.fence
@pytest.mark.ras
@pytest.mark.skip(reason="RAS Passport creation is broken")
class TestRasDrs:
    @classmethod
    def setup_class(cls):
        cls.indexd = Indexd()
        cls.fence = Fence()
        cls.ras = RAS()
        cls.variables = {}
        cls.variables["created_indexd_dids"] = []

        cls.env_vars = [
            "CI_TEST_RAS_USERID",
            "CI_TEST_RAS_PASSWORD",
            "CLIENT_ID",
            "SECRET_ID",
        ]
        cls.scope = "openid profile email ga4gh_passport_v1"
        cls.ga4gh_url = f"{pytest.namespace}.planx-pla.net/ga4gh/drs/v1/objects"
        # Upload new Indexd records
        # Adding indexd files
        for key, val in indexd_files.items():
            indexd_record = cls.indexd.create_records(records={key: val})
            cls.variables["created_indexd_dids"].append(indexd_record[0]["did"])

    @classmethod
    def teardown_class(cls):
        # Deleting indexd records
        cls.indexd.delete_records(cls.variables["created_indexd_dids"])

    # TODO: Need to finish test case, once passports can be retrieved for RAS
    @pytest.mark.wip("RAS Passport creation is broken")
    def test_single_valid_passport_single_visa(self, page: Page):
        """
        Scenario: Send DRS request - Single Valid Passport Single VISA
        Steps:
            1. Validate required RAS credentials are present.
            2. Get the access token based on client_id, secret_id and RAS credentials.
            3. Get the passport.
            4. Retrieve indexd record using accessible_drs_object_url.
            5. Validate the response is 200 and contains url key in response.
        """
        # Validate creds required for test are defined as env variable
        creds_dict = self.ras.validate_creds(test_creds=self.env_vars)

        # Get tokens
        tokens = self.ras.get_tokens(
            client_id=creds_dict["CLIENT_ID"],
            secret_id=creds_dict["SECRET_ID"],
            scope=self.scope,
            username=creds_dict["CI_TEST_RAS_USERID"],
            password=creds_dict["CI_TEST_RAS_PASSWORD"],
            page=page,
        )

        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        id_token = tokens["id_token"]
        passport = self.ras.get_passport(access_token=access_token)
        accessible_drs_object_url = f"https://{self.ga4gh_url}/{indexd_files['Permission_test_user_should_have']['did']}/access/s3"

        post_durations = []

        for i in range(2):
            start_time = time.time
            drs_access_req = requests.post(
                url=accessible_drs_object_url, data={"passports": [passport]}
            )

    # TODO: Need to finish test case, once passports can be retrieved for RAS
    @pytest.mark.wip("RAS Passport creation is broken")
    def test_single_valid_passport_single_visa_no_permission(self):
        """
        Scenario: Send DRS request - Single Valid Passport Single VISA With No Permission
        Steps:
            1. Validate required RAS credentials are present.
            2. Get the access token based on client_id, secret_id and RAS credentials (without permission).
            3. Get the passport.
            4. Retrieve indexd record using accessible_drs_object_url.
            5. Validate the response is 401.
        """
        # TODO: this needs to be gone, refer to gen3-qa code
        creds_dict = self.ras.validate_creds(test_creds=self.env_vars)

        # Get tokens
        tokens = self.ras.get_tokens(
            client_id=creds_dict["CLIENT_ID"],
            secret_id=creds_dict["SECRET_ID"],
            scope=self.scope,
            username=creds_dict["CI_TEST_RAS_USERID_2"],
            password=creds_dict["CI_TEST_RAS_PASSWORD_2"],
        )

        access_token = tokens["access_token"]
        passport_with_no_permission = self.ras.get_passport(access_token=access_token)

        accessible_drs_object_url = f"https://{self.ga4gh_url}/{indexd_files['Permission_test_user_should_not_have']['did']}/access/s3"

        drs_access_req = requests.post(
            url=accessible_drs_object_url,
            data={"passports": [passport_with_no_permission]},
        )

        assert "401" in drs_access_req, f"Expected 401, but got {drs_access_req}"

    # TODO: Need to finish test case, once passports can be retrieved for RAS
    @pytest.mark.wip("RAS Passport creation is broken")
    def test_single_valid_passport_single_visa_incorrect_access(self):
        """
        Scenario: Send DRS request - Single Valid Passport Single VISA With Incorrect Access
        Steps:
            1. Validate required RAS credentials are present.
            2. Get the access token based on client_id, secret_id and RAS credentials.
            3. Get the passport.
            4. Retrieve indexd record using inaccessible_drs_object_url.
            5. Validate the response is 401.
        """
        # Validate creds required for test are defined as env variable
        creds_dict = self.ras.validate_creds(test_creds=self.env_vars)

        # Get tokens
        tokens = self.ras.get_tokens(
            client_id=creds_dict["CLIENT_ID"],
            secret_id=creds_dict["SECRET_ID"],
            scope=self.scope,
            username=creds_dict["CI_TEST_RAS_USERID"],
            password=creds_dict["CI_TEST_RAS_PASSWORD"],
        )

        access_token = tokens["access_token"]
        passport = self.ras.get_passport(access_token=access_token)

        accessible_drs_object_url = f"https://{self.ga4gh_url}/{indexd_files['Permission_test_user_should_have']['did']}/access/s3"

        drs_access_req = requests.post(
            url=accessible_drs_object_url, data={"passports": [passport]}
        )

        assert "401" in drs_access_req, f"Expected 401, but got {drs_access_req}"

    # TODO: Need to finish test case, once passports can be retrieved for RAS
    @pytest.mark.wip("RAS Passport creation is broken")
    def test_single_valid_passport_invalid_signature(self):
        """
        Scenario: Send DRS request - Single Valid Passport With Invalid Signature
        Steps:
            1. Validate required RAS credentials are present.
            2. Get the access token based on client_id, secret_id and RAS credentials.
            3. Get the passport with invalid signature
            4. Retrieve indexd record using accessible_drs_object_url.
            5. Validate the response is 401.
        """
        return

    # TODO: Need to finish test case, once passports can be retrieved for RAS
    @pytest.mark.wip("RAS Passport creation is broken")
    def test_get_access_token_from_refresh_token(self):
        """
        Scenario: Get Access Token from Refresh Token
        Steps:
            1. Validate required RAS credentials are present.
            2. Get the refresh token based on client_id, secret_id and RAS credentials.
            3. Get the passport with refresh token
            4. Retrieve indexd record using accessible_drs_object_url.
            5. Validate the response is 200 and contains url key in response.
        """
        return
