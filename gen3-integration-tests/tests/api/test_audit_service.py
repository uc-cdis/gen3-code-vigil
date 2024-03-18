"""
AUDIT SERVICE
"""
import os
import time
import pytest
import math
import datetime

from gen3.auth import Gen3Auth
from cdislogging import get_logger

from services.audit import Audit
from services.indexd import Indexd
from services.fence import Fence
from pages.login import LoginPage
from utils.gen3_admin_tasks import update_audit_service_logging

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.audit
class TestAuditService:
    @classmethod
    def setup_class(cls):
        assert update_audit_service_logging(pytest.namespace, "true")

    @classmethod
    def teardown_class(self):
        assert update_audit_service_logging(pytest.namespace, "false")

    def test_audit_unauthorized_log_query(self):
        """Audit: unauthorized log query"""
        audit = Audit()
        timestamp = math.floor(time.mktime(datetime.datetime.now().timetuple()))
        params = ["start={}".format(timestamp)]

        # `mainAcct` does not have access to query any audit logs
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        audit.audit_query(
            "presigned_url", auth, params, 403, "Main-Account Presigned-URL"
        )
        audit.audit_query("login", auth, params, 403, "Main-Account Login")

        # `auxAcct1` has access to query presigned_url audit logs, not login
        auth = Gen3Auth(refresh_token=pytest.api_keys["auxAcct1_account"])
        audit.audit_query("presigned_url", auth, params, 200, "auxAcct1 Presigned-URL")
        audit.audit_query("login", auth, params, 403, "auxAcct1 Login")

        # `auxAcct2` has access to query login audit logs, not presigned_url
        auth = Gen3Auth(refresh_token=pytest.api_keys["auxAcct2_account"])
        audit.audit_query("presigned_url", auth, params, 403, "auxAcct2 Presigned-URL")
        audit.audit_query("login", auth, params, 200, "auxAcct2 Login")

    def test_audit_homepage_login_events(self, page):
        """Audit: homepage login events"""
        audit = Audit()
        login_page = LoginPage()
        timestamp = math.floor(time.mktime(datetime.datetime.now().timetuple()))
        params = ["start={}".format(timestamp)]

        # Perform login and logout operations using main_account to create a login record for audit service to access
        logger.info("Logging in with mainAcct")
        login_page.go_to(page)
        login_page.login(page)
        login_page.logout(page)

        # Check the query results with auxAcct2 user
        auth = Gen3Auth(refresh_token=pytest.api_keys["auxAcct2_account"])
        expectedResults = {
            "username": "cdis.autotest@gmail.com",
            "idp": "google",
            "client_id": None,
            "status_code": 302,
        }
        assert audit.checkQueryResults("login", auth, params, expectedResults)

    def test_audit_download_presignedURL_events(self):
        """Audit: download presigned URL events"""
        indexd = Indexd()
        main_auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        dummy_auth = Gen3Auth(refresh_token=pytest.api_keys["auxAcct1_account"])
        did_records = []
        did_mapping = {}

        try:
            files = {
                "private": {
                    "filename": "private_file",
                    "link": "s3://cdis-presigned-url-test/testdata",
                    "md5": "73d643ec3f4beb9020eef0beed440ad0",
                    "authz": ["/programs/jnkns"],
                    "size": 9,
                },
                "public": {
                    "filename": "public_file",
                    "link": "s3://cdis-presigned-url-test/testdata",
                    "md5": "73d643ec3f4beb9020eef0beed440ad1",
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
                main_auth,
                200,
                file_type,
                dummy_auth,
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
                did_mapping[file_type], {}, 401, file_type, dummy_auth, expectedResults
            )

            # Private File - mainAcct fails to request a presigned URL with a file that doesn't exists
            expectedResults = {
                "action": "download",
                "username": "cdis.autotest@gmail.com",
                "guid": "123",
                "status_code": 404,
            }
            self.perform_presigned_check(
                "123", main_auth, 404, file_type, dummy_auth, expectedResults
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
                did_mapping[file_type], {}, 200, file_type, dummy_auth, expectedResults
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
        params = ["start={}".format(timestamp)]
        # Create Signed URL record
        fence.createSignedUrl(did, main_auth, expectedCode, file_type)
        assert audit.checkQueryResults(
            "presigned_url", dummy_auth, params, expectedResults
        )
