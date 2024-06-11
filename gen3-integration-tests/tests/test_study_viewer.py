import pytest
import os
import requests
import json
import utils.gen3_admin_tasks as gat

from utils import logger
from playwright.sync_api import Page, expect
from pages.login import LoginPage
from services.requestor import Requestor
from utils.test_execution import screenshot


class TestPFBExport(object):
    variables = {}

    def setup_class(cls):
        cls.variables["request_ids"] = []
        cls.variables["username"] = pytest.users["user0_account"]
        cls.variables["policy"] = "programs.jnkns.projects.jenkins_accessor"

    def teardown_class(cls):
        requestor = Requestor()
        # # revoke access for user0 in arborist after the test is finished
        # gat.revoke_arborist_policy(pytest.namespace, cls.variables["username"], cls.variables["policy"])

        # # Delete all the request_ids after the test is finished
        # for request_id in cls.variables["request_ids"]:
        #     requestor.request_delete(request_id)

    def test_unauthorized_user_request_access(self, page):
        """
        Scenario: Request Access without logging in
        Steps:
            1. Go to StudyViewer Page
            2. Click 'Learn More' button and see 'Login to Request Access' button
            3. click 'Login to Request Access' button which takes you to Login Page
            4. Login with 'user0_account' user
            5. Go to StudyViewer Page. click on 'Learn More' button
            6. See 'Request Access' button
        """
        pass

    def test_user_requests_access(self, page):
        """
        Scenario: User logs in and requests access
        Steps:
            1. Login with 'user0_account' user and go to StudyViewer Page
            2. Click 'Learn More' button and click on 'Request Access' button
            3. Update the 'request_id' to Approved State and check if you see 'Request Access' button disabled
            4. Update the 'request_id' to Signed State and check if you see 'Request Access' button enabled
            5. Click Download button
        """
        pass

    def test_user_download_access(self, page):
        """
        Scenario: User logs in and downloads the study
        Steps:
            1. Login with'user0_account' user and go to StudyViewer Page
            2. Click 'Learn More' button and see 'Download' button
        """
        pass
