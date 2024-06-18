import pytest
import os
import requests
import json
import utils.gen3_admin_tasks as gat
import time

from utils import logger
from playwright.sync_api import Page, expect
from pages.login import LoginPage
from pages.study_viewer import StudyViewerPage
from services.requestor import Requestor
from utils.test_execution import screenshot


class TestStudyViewer(object):
    variables = {}

    def setup_class(cls):
        cls.variables["request_ids"] = []
        cls.variables["username"] = "dcf-integration-test-0@planx-pla.net"
        cls.variables["policy"] = "programs.jnkns.projects.jenkins_accessor"

    def teardown_class(cls):
        requestor = Requestor()
        # revoke access for user0 in arborist after the test is executed
        logger.info(f"Revoking access for user ...")
        gat.revoke_arborist_policy(
            pytest.namespace, cls.variables["username"], cls.variables["policy"]
        )

        # Delete all the request_ids after the test is executed
        for request_id in cls.variables["request_ids"]:
            requestor.request_delete(request_id)
            logger.info(f"Request {request_id} deleted")

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
        login_page = LoginPage()
        study_viewer = StudyViewerPage()
        # Navigate to study viewer page before logging in
        study_viewer.go_to(page)
        study_viewer.click_show_details(page)
        # See login to request access button on the dataset
        study_viewer.click_login_request_access_button(page)
        # Login with user0_account user
        login_page.login(page, user="user0_account")
        # Navigate to study viewer page
        study_viewer.go_to(page)
        study_viewer.click_show_details(page)
        # Check if 'request_access' button is visible
        request_access = page.locator(study_viewer.REQUEST_ACCESS_BUTTON)
        request_access.wait_for()
        screenshot(page, "RequestAccessButton")
        assert request_access.is_visible()

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
        login_page = LoginPage()
        study_viewer = StudyViewerPage()
        requestor = Requestor()
        # Login with user0_account user
        login_page.go_to(page)
        login_page.login(page, user="user0_account")
        # Navigate to study viewer page
        study_viewer.go_to(page)
        study_viewer.click_show_details(page)
        # Click on request_access button
        study_viewer.click_request_access_button(page)
        # Get request_id from requestor db
        time.sleep(20)
        request_id = requestor.get_request_id("user0_account")
        self.variables["request_id"].append(request_id)
        requestor.request_approved(request_id)
        status = requestor.get_request_status(request_id)
        if status == "Approved":
            logger.info(
                "Request Status : Approved. Lets update the request to 'Signed' Status"
            )
        else:
            logger.info(f"Request Status : {status}")
        time.sleep(5)
        requestor.request_signed(request_id)
        page.reload()
        download_button = page.locator(study_viewer.DOWNLOAD_BUTTON)
        assert download_button.is_visible()

    def test_user_download_access(self, page):
        """
        Scenario: User logs in and downloads the study
        Steps:
            1. Login with'user0_account' user and go to StudyViewer Page
            2. Click 'Learn More' button and see 'Download' button
        """
        login_page = LoginPage()
        study_viewer = StudyViewerPage()
        login_page.go_to(page)
        login_page.login(page, user="user0_account")
        study_viewer.go_to(page)
        study_viewer.click_show_details(page)
        download_button = page.locator(study_viewer.DOWNLOAD_BUTTON)
        assert download_button.is_visible()
