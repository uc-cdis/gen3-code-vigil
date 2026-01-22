"""
OAUTH2
"""

import base64
import json
import os
import re

import pytest
from pages.login import LoginPage
from playwright.sync_api import Page
from services.fence import Fence
from utils import logger


@pytest.mark.skipif(
    "fence" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.fence
class TestLoginAuthorizedUsers:
    def test_new_user_allowed(self):
        """
        Scenario: New user is allowed to login
        Steps:
            1. Make sure fence config ALLOW_NEW_USER_ON_LOGIN is set to true
            2. Login using a new user
            3. Verify user is able to login and can be accessed by main_account user using /admin/user endpoint
        """
        return

    def test_inactive_user_cannot_login(self):
        """
        Scenario: Inactive user cannot login
        Steps:
            1. Make sure fence config ALLOW_NEW_USER_ON_LOGIN is set to true
            2. Use main_account user to make an existing user active status to inactive using /admin/user/{username}/soft endpoint
            3. Login with inactive user.
            4. Verify login fails with 401 error.
            5. Use main_account user to make the same existing user active status to active using /admin/user endpoint
            6. Login using a new user
            7. Verify user is able to login
        """
        return

    def test_access_admin_user_endpoint(self):
        """
        Scenario: Validate only users with fence admin permissions can access /admin/user/{username} endpoint
        Steps:
            1. Login with indexing_account user and perform get request on /admin/user/{username} endpoint
            2. Verify the endpoint is not accessible by indexing_account (403 error) as it doesn't have fence admin permission
            3. Login with main_account user and perform get request on /admin/user/{username} endpoint
            4. Verify the endpoint is accessible by main_account as it has fence admin permission
            5. Perform a post request for /admin/user/{username}, it should fail with duplicate user error (500 error)
        """
        return

    def test_delete_request_for_soft_endpoint(self):
        """
        Scenario: Perform delete request for /admin/user/{username}/soft endpoint
        Steps:
            1. Login with main_account user and perform a get request for an active user using /admin/user/{username} endpoint
            2. Verify the user is in active status
            3. Perform the delete request using /admin/user/{username}/soft endpoint
            4. Perform a get request using /admin/user/{username} endpoint and verify user is in inactive status
            5. Again perform the delete request for inactive user using /admin/user/{username}/soft endpoint
            6. Verify the request fails
            7. Perform the delete request using /admin/user/{username}/soft endpoint for a user that doesn't exists
            8. Verify the request fails
        """
        return

    # NOTE: Fence deployment roll would be needed. Need to isolate this test from all other CI tests
    def test_new_user_is_not_allowed(self):
        """
        Scenario: New user is allowed to login
        Steps:
            1. Make sure fence config ALLOW_NEW_USER_ON_LOGIN is set to false
            2. Login using a new user
            3. Verify user fails to login with 401 error
            4. Login with main_account user (active user) and verify login is successful
        """
        return
