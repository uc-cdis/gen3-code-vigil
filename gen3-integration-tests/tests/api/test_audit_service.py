"""
AUDIT SERVICE
"""
import os
import time
import pytest
import math
import datetime
import re

from cdislogging import get_logger

from services.audit import Audit
from services.indexd import Indexd
from services.fence import Fence
from pages.login import LoginPage
from utils.gen3_admin_tasks import update_audit_service_logging
from playwright.sync_api import Page, expect

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
        """Audit: unauthorized log query
        Perform audit query using various users having different roles"""
        audit = Audit()
        timestamp = math.floor(time.mktime(datetime.datetime.now().timetuple()))
        params = ["start={}".format(timestamp)]

        # `mainAcct` does not have access to query any audit logs
        audit.audit_query(
            "presigned_url", "main_account", params, 403, "Main-Account Presigned-URL"
        )
        audit.audit_query("login", "main_account", params, 403, "Main-Account Login")

        # `auxAcct1` has access to query presigned_url audit logs, not login
        audit.audit_query(
            "presigned_url", "auxAcct1_account", params, 200, "auxAcct1 Presigned-URL"
        )
        audit.audit_query("login", "auxAcct1_account", params, 403, "auxAcct1 Login")

        # `auxAcct2` has access to query login audit logs, not presigned_url
        audit.audit_query(
            "presigned_url", "auxAcct2_account", params, 403, "auxAcct2 Presigned-URL"
        )
        audit.audit_query("login", "auxAcct2_account", params, 200, "auxAcct2 Login")

    def test_audit_homepage_login_events(self, page: Page):
        """Audit: homepage login events
        Login to homepage and query in Audit for login events"""
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
        expectedResults = {
            "username": "cdis.autotest@gmail.com",
            "idp": "google",
            "client_id": None,
            "status_code": 302,
        }
        assert audit.checkQueryResults(
            "login", "auxAcct2_account", params, expectedResults
        )

    def test_audit_oidc_login_events(self, page: Page):
        """Perform login using ORCID and validate audit entry
        NOTE : This test requires CI_TEST_ORCID_ID & CI_TEST_ORCID_PASSWORD
        secrets to be configured with ORCID credentials"""
        audit = Audit()
        login_page = LoginPage()
        timestamp = math.floor(time.mktime(datetime.datetime.now().timetuple()))
        params = ["start={}".format(timestamp)]

        # Perform login and logout operations using main_account to create a login record for audit service to access
        logger.info("Logging in with ORCID Test User")
        login_page.go_to(page)
        login_button = page.get_by_role(
            "button",
            name=re.compile(r"ORCID Login", re.IGNORECASE),
        )
        expect(login_button).to_be_visible(timeout=5000)
        login_button.click()
        page.wait_for_timeout(5000)

        # Handle the Cookie Settings Pop-Up
        try:
            page.click('text="Reject Unnecessary Cookies"')
            time.sleep(2)
        except:
            logger.info("Either Cookie Pop up is not present or unable to click on it")

        # Perform ORCID Login
        login_button = page.locator("input#username")
        expect(login_button).to_be_visible(timeout=5000)
        page.type('input[id="username"]', os.environ["CI_TEST_ORCID_ID"])
        page.type('input[id="password"]', os.environ["CI_TEST_ORCID_PASSWORD"])
        page.click('text="SIGN IN"')
        page.wait_for_timeout(3000)
        page.screenshot(path="output/AfterLogin.png", full_page=True)

        # Wait for login to perform and handle any pop ups if any
        page.wait_for_selector("//div[@class='top-bar']//a[3]", state="attached")
        login_page.handle_popup(page)
        page.screenshot(path="output/AfterPopUpAccept.png", full_page=True)

        # Perform Logout
        login_page.logout(page)

        # Check the query results with auxAcct2 user
        expectedResults = {
            "username": os.environ["CI_TEST_ORCID_ID"],
            "idp": "fence",
            "fence_idp": "orcid",
            "client_id": None,
            "status_code": 302,
        }
        assert audit.checkQueryResults(
            "login", "auxAcct2_account", params, expectedResults
        )

    def test_audit_download_presignedURL_events(self):
        """Audit: download presigned URL events
        Create preSignedUrls for different files and validate corresponding
        audit log enteries are present"""
        indexd = Indexd()
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
        params = ["start={}".format(timestamp)]
        # Create Signed URL record
        fence.createSignedUrl(did, main_auth, expectedCode, file_type)
        assert audit.checkQueryResults(
            "presigned_url", dummy_auth, params, expectedResults
        )
