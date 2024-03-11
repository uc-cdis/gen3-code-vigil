"""
AUDIT SERVICE
"""
import os
import time
import pytest
import math
import datetime

from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from cdislogging import get_logger

from services.audit import Audit

# from services.indexd import Indexd
from pages.login import LoginPage
from utils.gen3_admin_tasks import update_audit_service_logging

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.audit
class TestAuditService:
    def setup_method():
        assert update_audit_service_logging(pytest.namespace, "true")

    def teardown_method():
        assert update_audit_service_logging(pytest.namespace, "false")

    def test_audit_service(self, page):
        audit = Audit()
        login_page = LoginPage()
        timestamp = math.floor(time.mktime(datetime.datetime.now().timetuple()))
        logger.info(timestamp)
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
