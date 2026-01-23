"""
OAUTH2
"""

import pytest
import utils.gen3_admin_tasks as gat
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
    @classmethod
    def setup_class(cls):
        cls.login_page = LoginPage()
        cls.fence = Fence()

        # Add new user to pytest.users
        pytest.users["authorized_user_1"] = "authorized-user-1@example.org"
        pytest.users["authorized_user_2"] = "authorized-user-2@example.org"

    # @pytest.mark.skipif(
    #     not pytest.is_allow_new_user_on_login_enabled,
    #     reason="ALLOW_NEW_USER_ON_LOGIN is not set to true",
    # )
    def test_new_user_allowed(self, page: Page):
        """
        Scenario: New user is allowed to login
        Steps:
            1. Make sure fence config ALLOW_NEW_USER_ON_LOGIN is set to true
            2. Login using authorized_user_1 user
            3. Verify authorized_user_1 user is able to login and can be accessed by main_account user using /admin/user endpoint
        """
        logger.info("Logging in using authorized_user_1 user")
        self.login_page.go_to(page)
        self.login_page.login(page, user="authorized_user_1")
        self.login_page.logout(page)
        logger.info("Verifying authorized_user_1 user is present")
        response = self.fence.verify_authorized_username(
            verify_username="authorized_user_1"
        )
        assert (
            response.status_code == 200
        ), f"Expected status to be 200, but got {response.status_code}"
        assert response.json()[
            "active"
        ], f"Expected user status to be True, but got {response.json()["active"]}"

    # @pytest.mark.skipif(
    #     not pytest.is_allow_new_user_on_login_enabled,
    #     reason="ALLOW_NEW_USER_ON_LOGIN is not set to true",
    # )
    def test_inactive_user_cannot_login(self, page: Page):
        """
        Scenario: Inactive user cannot login
        Steps:
            1. Make sure fence config ALLOW_NEW_USER_ON_LOGIN is set to true
            2. Use main_account user to make an existing authorized_user_1 user active status to inactive using /admin/user/{username}/soft endpoint
            3. Login with inactive user.
            4. Verify login fails with 401 error.
            5. Activate authorized_user_1 user again
            6. Login using a authorized_user_1 user
            7. Verify authorized_user_1 user is able to login
        """
        logger.info("Inactivating authorized_user_1 user")
        response = self.fence.inactivate_user(username="authorized_user_1")
        assert (
            response.status_code == 200
        ), f"Expected status to be 200, but got {response.status_code}"
        self.login_page.go_to(page)
        self.login_page.login(
            page, user="authorized_user_1", validate_username_locator=False
        )
        logger.info(page.content())

    # @pytest.mark.skipif(
    #     not pytest.is_allow_new_user_on_login_enabled,
    #     reason="ALLOW_NEW_USER_ON_LOGIN is not set to true",
    # )
    def test_access_admin_user_endpoint(self):
        """
        Scenario: Validate only users with fence admin permissions can access /admin/user/{username} endpoint
        Steps:
            1. Using indexing_account user perform get request on /admin/user/{username} endpoint
            2. Verify the endpoint is not accessible by indexing_account (403 error) as it doesn't have fence admin permission
            3. Using main_account user perform get request on /admin/user/{username} endpoint
            4. Verify the endpoint is accessible by main_account as it has fence admin permission
            5. Perform a post request for /admin/user, it should fail with duplicate user error (500 error)
        """
        logger.info("Verifying authorized_user_1 status using indexing_account")
        response = self.fence.verify_authorized_username(
            verify_username="authorized_user_1", user="indexing_account"
        )
        assert (
            response.status_code == 403
        ), f"Expected status to be 403, but got {response.status_code}"
        logger.info("Verifying authorized_user_1 user is present using main_account")
        response = self.fence.verify_authorized_username(
            verify_username="authorized_user_1"
        )
        assert (
            response.status_code == 200
        ), f"Expected status to be 200, but got {response.status_code}"
        assert response.json()[
            "active"
        ], f"Expected user status to be True, but got {response.json()["active"]}"
        self.fence.create_user(username="authorized_user_1")
        logger.info("Performing authorized_user_1 user creation using main_account")
        response = self.fence.create_user(username="authorized_user_1")
        assert (
            response.status_code == 400
        ), f"Expected status to be 400, but got {response.status_code}"
        msg = "Error: user already exist"
        assert (
            msg in response.content.decode()
        ), f"Expected {msg}, but got {response.content}"

    # @pytest.mark.skipif(
    #     not pytest.is_allow_new_user_on_login_enabled,
    #     reason="ALLOW_NEW_USER_ON_LOGIN is not set to true",
    # )
    def test_delete_request_for_soft_endpoint(self):
        """
        Scenario: Perform delete request for /admin/user/{username}/soft endpoint
        Steps:
            1. Login with main_account user and perform a get request for authorized_user_1 user using /admin/user/{username} endpoint
            2. Verify the user is in active status
            3. Perform the delete request using /admin/user/{username}/soft endpoint to inactivate authorized_user_1
            4. Perform a get request using /admin/user/{username} endpoint and verify authorized_user_1 user is inactivated
            5. Again perform the delete request for inactive user using /admin/user/{username}/soft endpoint
            6. Verify the request fails
            7. Perform the delete request using /admin/user/{username}/soft endpoint for a authorized_user_2 user that doesn't exists
            8. Verify the request fails
        """
        logger.info("Verifying authorized_user_1 user is present")
        response = self.fence.verify_authorized_username(
            verify_username="authorized_user_1"
        )
        assert (
            response.status_code == 200
        ), f"Expected status to be 200, but got {response.status_code}"
        assert response.json()[
            "active"
        ], f"Expected user status to be True, but got {response.json()["active"]}"
        logger.info("Inactivating authorized_user_1 user")
        response = self.fence.inactivate_user(username="authorized_user_1")
        assert (
            response.status_code == 200
        ), f"Expected status to be 200, but got {response.status_code}"
        logger.info("Verifying authorized_user_1 user is inactivated")
        response = self.fence.verify_authorized_username(
            verify_username="authorized_user_1"
        )
        assert (
            response.status_code == 200
        ), f"Expected status to be 200, but got {response.status_code}"
        assert not response.json()[
            "active"
        ], f"Expected user status to be False, but got {response.json()["active"]}"
        logger.info("Attempting again to Inactivate authorized_user_1 user")
        response = self.fence.inactivate_user(username="authorized_user_1")
        assert (
            response.status_code == 200
        ), f"Expected status to be 200, but got {response.status_code}"
        logger.info("Inactivating authorized_user_2 user which doesnt exist")
        response = self.fence.inactivate_user(username="authorized_user_2")
        assert (
            response.status_code == 404
        ), f"Expected status to be 200, but got {response.status_code}"
        msg = f"user {pytest.users["authorized_user_2"]} not found"
        assert (
            msg in response.content.decode()
        ), f"Expected {msg}, but got {response.content}"

    @pytest.mark.skip(
        reason="Fence deployment roll would be needed. Need to isolate this test from all other CI tests"
    )
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
