"""
RAS DRS
"""

import os
import pytest
import requests
import time

from cdislogging import get_logger
from services.indexd import Indexd
from services.fence import Fence
from services.ras import RAS

from gen3.auth import Gen3Auth
from playwright.sync_api import Page

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))

indexd_files = {
    "Permission_test_user_should_have": {
        "acl": [],
        "authz": ["/programs/phs002409.c1"],
        "filename": "ras_test_file",
        "md5": "587efb5d96f695710a8df9c0dbb96eb0",  # pragma: allowlist secret
        "size": 15,
        "form": "object",
        "urls": [
            "s3://cdis-presigned-url-test/testdata",
            "gs://cdis-presigned-url-test/testdata",
        ],
    },
    "Permission_test_user_should_not_have": {
        "acl": [],
        "authz": ["/programs/phs002410.c1"],
        "filename": "ras_test_file",
        "md5": "587efb5d96f695710a8df9c0dbb96eb0",  # pragma: allowlist secret
        "size": 15,
        "form": "object",
        "urls": [
            "s3://cdis-presigned-url-test/testdata",
            "gs://cdis-presigned-url-test/testdata",
        ],
    },
}


@pytest.mark.indexd
class TestRasDrs:
    indexd = Indexd()
    fence = Fence()
    ras = RAS()

    env_vars = ["CI_TEST_RAS_USERID", "CI_TEST_RAS_PASSWORD", "CLIENT_ID", "SECRET_ID"]
    scope = "openid profile email ga4gh_passport_v1"
    ga4gh_url = f"{pytest.namespace}.planx-pla.net/ga4gh/drs/v1/objects"

    @classmethod
    def setup_class(cls):
        auth = Gen3Auth(refresh_token=pytest.api_keys["indexing_account"])
        cls.access_token = auth.get_access_token()

        # Upload new Indexd records
        # Adding indexd files
        for key, val in indexd_files.items():
            indexd_record = cls.indexd.create_files(
                files={key: val}, access_token=cls.access_token
            )
            indexd_files[key]["did"] = indexd_record[0]["did"]
            indexd_files[key]["rev"] = indexd_record[0]["rev"]

    @classmethod
    def teardown_class(cls):
        # Deleting indexd records
        cls.indexd.delete_file_indices(records=indexd_files)

    def test_single_valid_passport_single_visa(self, page: Page):
        """
        Scenario: Send DRS request - Single Valid Passport Single VISA
        Steps:
            1.
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

    '''def test_single_valid_passport_single_visa_no_permission(self):
        """
        Scenario: Send DRS request - Single Valid Passport Single VISA With No Permission
        Steps:
            1.
        """
        # TODO: this needs to be gone, refer to gen3-qa code
        creds_dict = self.ras.validate_creds(test_creds=self.env_vars)

        # Get tokens
        tokens = self.ras.get_tokens(client_id=creds_dict["CLIENT_ID"],
                                     secret_id=creds_dict["SECRET_ID"],
                                     scope=self.scope,
                                     username=creds_dict["CI_TEST_RAS_USERID_2"],
                                     password=creds_dict["CI_TEST_RAS_PASSWORD_2"])

        access_token = tokens["access_token"]
        passport_with_no_permission = self.ras.get_passport(access_token=access_token)

        accessible_drs_object_url = f"https://{self.ga4gh_url}/{indexd_files['Permission_test_user_should_not_have']['did']}/access/s3"

        drs_access_req = requests.post(url=accessible_drs_object_url, data={"passports": [passport_with_no_permission]})

        assert "401" in drs_access_req, f"Expected 401, but got {drs_access_req}"


    def test_single_valid_passport_single_visa_incorrect_access(self):
        """
        Scenario: Send DRS request - Single Valid Passport Single VISA With Incorrect Access
        Steps:
            1.
        """
        # Validate creds required for test are defined as env variable
        creds_dict = self.ras.validate_creds(test_creds=self.env_vars)

        # Get tokens
        tokens = self.ras.get_tokens(client_id=creds_dict["CLIENT_ID"],
                                     secret_id=creds_dict["SECRET_ID"],
                                     scope=self.scope,
                                     username=creds_dict["CI_TEST_RAS_USERID"],
                                     password=creds_dict["CI_TEST_RAS_PASSWORD"])

        access_token = tokens["access_token"]
        passport = self.ras.get_passport(access_token=access_token)

        accessible_drs_object_url = f"https://{self.ga4gh_url}/{indexd_files['Permission_test_user_should_have']['did']}/access/s3"

        drs_access_req = requests.post(url=accessible_drs_object_url, data={"passports": [passport]})

        assert "401" in drs_access_req, f"Expected 401, but got {drs_access_req}"


    def test_single_valid_passport_invalid_signature(self):
        """
        Scenario: Send DRS request - Single Valid Passport With Invalid Signature
        Steps:
            1.
        """
        return

    def test_get_access_token_from_refresh_token(self):
        """
        Scenario: Get Access Token from Refresh Token
        Steps:
            1.
        """
        return'''
