"""
AUDIT SERVICE
"""

import datetime
import math
import os
import time

import pytest
from pages.login import LoginPage
from playwright.sync_api import Page
from services.audit import Audit
from services.fence import Fence
from services.indexd import Indexd
from utils import logger
from utils.gen3_admin_tasks import update_audit_service_logging


# audit deployment name is "audit-service" in adminvm and "audit-deployment" in gen3 helm
@pytest.mark.skipif(
    not any("audit" in key for key in pytest.deployed_services),
    reason="audit service is not running on this environment",
)
@pytest.mark.audit
@pytest.mark.ras
@pytest.mark.fence
class TestAuditService:
    @classmethod
    def setup_class(cls):
        if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
            assert update_audit_service_logging(
                "true", test_env_namespace=pytest.namespace
            )

    @classmethod
    def teardown_class(cls):
        if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
            assert update_audit_service_logging(
                "false", test_env_namespace=pytest.namespace
            )

    def test_audit_unauthorized_log_query(self):
        """
        Scenario: Unauthorized log query
        Steps:
            1. Call Audit log query for presignel_url and login types with below users:
                main account
                auxAcct1 account
                auxAcct2 account
            2. Users will get either 200 or 403 response based on the privileges on their account
        """
        audit = Audit()

        # `mainAcct` does not have access to query any audit logs
        audit.audit_query(
            "presigned_url",
            "main_account",
            403,
            "Main-Account Presigned-URL",
        )
        audit.audit_query(
            "login",
            "main_account",
            403,
            "Main-Account Login",
        )

        # `auxAcct1` has access to query presigned_url audit logs, not login
        audit.audit_query(
            "presigned_url",
            "dummy_one",
            200,
            "auxAcct1 Presigned-URL",
        )
        audit.audit_query(
            "login",
            "dummy_one",
            403,
            "auxAcct1 Login",
        )

        # `auxAcct2` has access to query login audit logs, not presigned_url
        audit.audit_query(
            "presigned_url",
            "smarty_two",
            403,
            "auxAcct2 Presigned-URL",
        )
        audit.audit_query(
            "login",
            "smarty_two",
            200,
            "auxAcct2 Login",
        )

    @pytest.mark.portal
    def test_audit_homepage_login_events(self, page: Page):
        """
        Scenario: Homepage login events
        Steps:
            1. Login to homepage with mainAcct user
            2. Call Audit log API using auxAcct2 user
            3. Check if entry for mainAcct user is present
        """
        audit = Audit()
        login_page = LoginPage()
        timestamp = math.floor(time.mktime(datetime.datetime.now().timetuple()))
        params = [
            "start={}".format(timestamp),
            f"username={pytest.users['main_account']}",
        ]

        # Perform login and logout operations using main_account to create a login record for audit service to access
        logger.info("Logging in with mainAcct")
        login_page.go_to(page)
        login_page.login(page)
        login_page.logout(page)

        # Check the query results with auxAcct2 user
        expected_results = {
            "username": pytest.users["main_account"],
            "idp": "google",
            "client_id": None,
            "status_code": 302,
        }
        assert audit.check_query_results(
            "login", "smarty_two", params, expected_results
        )

    def test_audit_oidc_login_events(self, page: Page):
        """
        Scenario: Perform login using ORCID and validate audit entry
        Steps :
            1. Login to homepage via ORCID using ORCID credentials
            2. Call Audit log API using auxAcct2 user
            3. Check if entry for ORCID user is present
        NOTE : This test requires CI_TEST_ORCID_ID & CI_TEST_ORCID_PASSWORD
        secrets to be configured with ORCID credentials
        """
        audit = Audit()
        login_page = LoginPage()
        timestamp = math.floor(time.mktime(datetime.datetime.now().timetuple()))
        params = [
            "start={}".format(timestamp),
            "username={}".format(os.environ["CI_TEST_ORCID_USERID"]),
        ]

        # Perform login and logout operations using main_account to create a login record for audit service to access
        logger.info("# Logging in with ORCID USER")
        login_page.go_to(page)

        # Perform Login
        login_page.login(page, idp="ORCID")

        # Perform Logout
        login_page.logout(page)

        # Check the query results with auxAcct2 user
        expected_results = {
            "username": os.environ["CI_TEST_ORCID_USERID"],
            "idp": "fence",
            "fence_idp": "orcid",
            "client_id": None,
            "status_code": 302,
        }
        assert audit.check_query_results(
            "login", "smarty_two", params, expected_results
        )

    @pytest.mark.indexd
    @pytest.mark.skipif(
        "indexd" not in pytest.deployed_services,
        reason="indexd is not running on this environment",
    )
    @pytest.mark.skipif(
        "fence" not in pytest.deployed_services,
        reason="fence is not running on this environment",
    )
    def test_audit_download_presignedURL_events(self):
        """
        Scenario: Download presigned URL events
        Steps:
            1. Create private and public files using Indexd
            2. Perform a download using Presigned_URL
            3. Call Audit log API using auxAcct2 user for presigned_url category
            4. Check audit logs are present for each download scenario
        """
        indexd = Indexd()
        did_records = []
        did_mapping = {}

        try:
            files = {
                "private": {
                    "file_name": "private_file",
                    "urls": ["s3://cdis-presigned-url-test/testdata"],
                    "hashes": {
                        "md5": "73d643ec3f4beb9020eef0beed440ad0"
                    },  # pragma: allowlist secret
                    "authz": ["/programs/jnkns"],
                    "size": 9,
                },
                "public": {
                    "file_name": "public_file",
                    "urls": ["s3://cdis-presigned-url-test/testdata"],
                    "hashes": {
                        "md5": "73d643ec3f4beb9020eef0beed440ad1"
                    },  # pragma: allowlist secret
                    "authz": ["/open"],
                    "size": 9,
                },
            }
            records = indexd.create_records(files)
            # Create List and Dictionary to capture did information of the public and private files
            for record in records:
                did_records.append(record["did"])
                did_mapping[record["file_name"]] = record["did"]
            logger.info(did_mapping)

            file_type = "private_file"
            # Private File - mainAcct succeffully requests a presigned URL
            expected_results = {
                "action": "download",
                "username": pytest.users["main_account"],
                "guid": did_mapping[file_type],
                "status_code": 200,
            }
            self.perform_presigned_check(
                did_mapping[file_type],
                "main_account",
                200,
                "dummy_one",
                expected_results,
            )

            # Private File - mainAcct fails to request a presigned URL with no authorization code
            expected_results = {
                "action": "download",
                "username": "anonymous",
                "guid": did_mapping[file_type],
                "status_code": 401,
            }
            self.perform_presigned_check(
                did_mapping[file_type],
                None,
                401,
                "dummy_one",
                expected_results,
            )

            # Private File - mainAcct fails to request a presigned URL with a file that doesn't exists
            expected_results = {
                "action": "download",
                "username": pytest.users["main_account"],
                "guid": "123",
                "status_code": 404,
            }
            self.perform_presigned_check(
                "123",
                "main_account",
                404,
                "dummy_one",
                expected_results,
            )

            file_type = "public_file"
            # Public File - mainAcct succeffully requests a presigned URL
            expected_results = {
                "action": "download",
                "username": "anonymous",
                "guid": did_mapping[file_type],
                "status_code": 200,
            }
            self.perform_presigned_check(
                did_mapping[file_type],
                None,
                200,
                "dummy_one",
                expected_results,
            )
        finally:
            indexd.delete_records(did_records)

    def perform_presigned_check(
        self, did, main_auth, expected_code, dummy_auth, expected_results
    ):
        """helper function to Create Signed URL and Query the audit logs for entry"""
        fence = Fence()
        audit = Audit()
        timestamp = math.floor(time.mktime(datetime.datetime.now().timetuple()))
        params = [
            "start={}".format(timestamp),
            "username={}".format(expected_results["username"]),
            "guid={}".format(expected_results["guid"]),
        ]
        # Create Signed URL record
        fence.create_signed_url(did, main_auth, expected_code)
        assert audit.check_query_results(
            "presigned_url", dummy_auth, params, expected_results
        )

    @pytest.mark.skipif(
        "nightly-build" not in pytest.hostname
        and os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL",
        reason="Test is being run on Helm and would run only on nightly-build",
    )
    def test_audit_ras_login_events(self, page: Page):
        """
        Scenario: Perform login using RAS and validate audit entry
        Steps : 1. Login to homepage via RAS using RAS credentials
                2. Call Audit log API using auxAcct2 user
                3. Check if entry for RAS user is present
        NOTE : This test requires CI_TEST_RAS_ID & CI_TEST_RAS_PASSWORD
        secrets to be configured with RAS credentials
        """
        #  Confirm CI_TEST_RAS_EMAIL and CI_TEST_RAS_PASSWORD are present in env
        assert "CI_TEST_RAS_EMAIL" in os.environ, "CI_TEST_RAS_EMAIL not found"
        assert "CI_TEST_RAS_PASSWORD" in os.environ, "CI_TEST_RAS_PASSWORD not found"
        audit = Audit()
        login_page = LoginPage()
        timestamp = math.floor(time.mktime(datetime.datetime.now().timetuple()))
        # RAS username is very flaky, so we use only start time as param and avoid username
        params = ["start={}".format(timestamp)]

        # Perform login and logout operations using main_account to create a login record for audit service to access
        logger.info("# Logging in with RAS USER")
        login_page.go_to(page)

        # Perform Login
        login_page.login(page, idp="RAS")

        # Perform Logout
        login_page.logout(page)

        # Check the query results with auxAcct2 user
        expected_results = {
            "username": str(os.environ["CI_TEST_RAS_EMAIL"].split("@")[0]),
            "idp": "ras",
            "client_id": None,
            "status_code": 302,
        }
        assert audit.check_query_results(
            "login", "smarty_two", params, expected_results
        )
