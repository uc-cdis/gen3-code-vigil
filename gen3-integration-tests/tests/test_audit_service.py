"""
AUDIT SERVICE
"""
import os
import time
import pytest
import math
import datetime

from utils import logger

from services.audit import Audit
from services.indexd import Indexd
from services.fence import Fence
from pages.login import LoginPage
from utils.gen3_admin_tasks import update_audit_service_logging
from playwright.sync_api import Page


@pytest.mark.audit
class TestAuditService:
    @classmethod
    def setup_class(cls):
        assert update_audit_service_logging(pytest.namespace, "true")

    @classmethod
    def teardown_class(cls):
        assert update_audit_service_logging(pytest.namespace, "false")

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
            "cdis.autotest@gmail.com",
            403,
            "Main-Account Presigned-URL",
        )
        audit.audit_query(
            "login",
            "main_account",
            "cdis.autotest@gmail.com",
            403,
            "Main-Account Login",
        )

        # `auxAcct1` has access to query presigned_url audit logs, not login
        audit.audit_query(
            "presigned_url",
            "auxAcct1_account",
            "dummy-one@planx-pla.net",
            200,
            "auxAcct1 Presigned-URL",
        )
        audit.audit_query(
            "login",
            "auxAcct1_account",
            "dummy-one@planx-pla.net",
            403,
            "auxAcct1 Login",
        )

        # `auxAcct2` has access to query login audit logs, not presigned_url
        audit.audit_query(
            "presigned_url",
            "auxAcct2_account",
            "smarty-two@planx-pla.net",
            403,
            "auxAcct2 Presigned-URL",
        )
        audit.audit_query(
            "login",
            "auxAcct2_account",
            "smarty-two@planx-pla.net",
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
        params = ["start={}".format(timestamp), "username=cdis.autotest@gmail.com"]

        # Perform login and logout operations using main_account to create a login record for audit service to access
        logger.info("Logging in with mainAcct")
        login_page.go_to(page)
        login_page.login(page)
        login_page.logout(page)

        # Check the query results with auxAcct2 user
        expectedResults = {
            "username": "cdis.autotest@gmail.com",
            "idp": "google",
            "client_id": None,
            "status_code": 302,
        }
        assert audit.check_query_results(
            "login", "auxAcct2_account", params, expectedResults
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
        expectedResults = {
            "username": os.environ["CI_TEST_ORCID_USERID"],
            "idp": "fence",
            "fence_idp": "orcid",
            "client_id": None,
            "status_code": 302,
        }
        assert audit.check_query_results(
            "login", "auxAcct2_account", params, expectedResults
        )

    @pytest.mark.indexd
    @pytest.mark.fence
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
                    "filename": "private_file",
                    "link": "s3://cdis-presigned-url-test/testdata",
                    "md5": "73d643ec3f4beb9020eef0beed440ad0",  # pragma: allowlist secret
                    "authz": ["/programs/jnkns"],
                    "size": 9,
                },
                "public": {
                    "filename": "public_file",
                    "link": "s3://cdis-presigned-url-test/testdata",
                    "md5": "73d643ec3f4beb9020eef0beed440ad1",  # pragma: allowlist secret
                    "authz": ["/open"],
                    "size": 9,
                },
            }
            records = indexd.create_files(files)
            # Create List and Dictionary to capture did information of the public and private files
            for record in records:
                did_records.append(record["did"])
                did_mapping[record["file_name"]] = record["did"]
            logger.info(did_mapping)

            file_type = "private_file"
            # Private File - mainAcct succeffully requests a presigned URL
            expectedResults = {
                "action": "download",
                "username": "cdis.autotest@gmail.com",
                "guid": did_mapping[file_type],
                "status_code": 200,
            }
            self.perform_presigned_check(
                did_mapping[file_type],
                "main_account",
                200,
                file_type,
                "auxAcct1_account",
                expectedResults,
            )

            # Private File - mainAcct fails to request a presigned URL with no authorization code
            expectedResults = {
                "action": "download",
                "username": "anonymous",
                "guid": did_mapping[file_type],
                "status_code": 401,
            }
            self.perform_presigned_check(
                did_mapping[file_type],
                None,
                401,
                file_type,
                "auxAcct1_account",
                expectedResults,
            )

            # Private File - mainAcct fails to request a presigned URL with a file that doesn't exists
            expectedResults = {
                "action": "download",
                "username": "cdis.autotest@gmail.com",
                "guid": "123",
                "status_code": 404,
            }
            self.perform_presigned_check(
                "123",
                "main_account",
                404,
                file_type,
                "auxAcct1_account",
                expectedResults,
            )

            file_type = "public_file"
            # Public File - mainAcct succeffully requests a presigned URL
            expectedResults = {
                "action": "download",
                "username": "anonymous",
                "guid": did_mapping[file_type],
                "status_code": 200,
            }
            self.perform_presigned_check(
                did_mapping[file_type],
                None,
                200,
                file_type,
                "auxAcct1_account",
                expectedResults,
            )
        finally:
            indexd.delete_files(did_records)

    def perform_presigned_check(
        self, did, main_auth, expectedCode, file_type, dummy_auth, expectedResults
    ):
        """helper function to Create Signed URL and Query the audit logs for entry"""
        fence = Fence()
        audit = Audit()
        timestamp = math.floor(time.mktime(datetime.datetime.now().timetuple()))
        params = [
            "start={}".format(timestamp),
            "username={}".format(expectedResults["username"]),
        ]
        # Create Signed URL record
        fence.createSignedUrl(did, main_auth, expectedCode, file_type)
        assert audit.check_query_results(
            "presigned_url", dummy_auth, params, expectedResults
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
        audit = Audit()
        login_page = LoginPage()
        timestamp = math.floor(time.mktime(datetime.datetime.now().timetuple()))
        params = [
            "start={}".format(timestamp),
            "username={}".format(os.environ["CI_TEST_RAS_USERID"].lower()),
        ]

        # Perform login and logout operations using main_account to create a login record for audit service to access
        logger.info("# Logging in with RAS USER")
        login_page.go_to(page)

        # Perform Login
        login_page.login(page, idp="RAS")

        # Perform Logout
        login_page.logout(page)

        # Check the query results with auxAcct2 user
        expectedResults = {
            "username": str(os.environ["CI_TEST_RAS_USERID"]).lower(),
            "idp": "ras",
            "client_id": None,
            "status_code": 302,
        }
        assert audit.check_query_results(
            "login", "auxAcct2_account", params, expectedResults
        )
