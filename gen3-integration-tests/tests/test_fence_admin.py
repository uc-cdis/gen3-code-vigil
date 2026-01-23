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
class TestFenceAdmin:
    @classmethod
    def setup_class(cls):
        cls.login_page = LoginPage()
        cls.fence = Fence()

        # Add new user to pytest.users
        pytest.users["fence_admin_1"] = "fence-admin-1@example.org"
        pytest.users["fence_admin_2"] = "fence-admin-2@example.org"

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
        logger.info("Verifying fence_admin_1 status using indexing_account")
        response = self.fence.verify_authorized_username(
            verify_username="fence_admin_1", user="indexing_account"
        )
        assert (
            response.status_code == 403
        ), f"Expected status to be 403, but got {response.status_code}"
        logger.info("Verifying fence_admin_1 user is present using main_account")
        response = self.fence.verify_authorized_username(
            verify_username="fence_admin_1"
        )
        assert (
            response.status_code == 200
        ), f"Expected status to be 200, but got {response.status_code}"
        assert response.json()[
            "active"
        ], f"Expected user status to be True, but got {response.json()["active"]}"
        self.fence.create_user(username="fence_admin_1")
        logger.info("Performing fence_admin_1 user creation using main_account")
        response = self.fence.create_user(username="fence_admin_1")
        assert (
            response.status_code == 400
        ), f"Expected status to be 400, but got {response.status_code}"
        msg = "Error: user already exist"
        assert (
            msg in response.content.decode()
        ), f"Expected {msg}, but got {response.content}"

    def test_delete_request_for_soft_endpoint(self):
        """
        Scenario: Perform delete request for /admin/user/{username}/soft endpoint
        Steps:
            1. Login with main_account user and perform a get request for fence_admin_1 user using /admin/user/{username} endpoint
            2. Verify the user is in active status
            3. Perform the delete request using /admin/user/{username}/soft endpoint to deactivate fence_admin_1
            4. Perform a get request using /admin/user/{username} endpoint and verify fence_admin_1 user is deactivated
            5. Again perform the delete request for inactive user using /admin/user/{username}/soft endpoint
            6. Verify the request fails
            7. Perform the delete request using /admin/user/{username}/soft endpoint for a fence_admin_2 user that doesn't exists
            8. Verify the request fails
        """
        logger.info("Verifying fence_admin_1 user is present")
        response = self.fence.verify_authorized_username(
            verify_username="fence_admin_1"
        )
        assert (
            response.status_code == 200
        ), f"Expected status to be 200, but got {response.status_code}"
        assert response.json()[
            "active"
        ], f"Expected user status to be True, but got {response.json()["active"]}"
        logger.info("deactivating fence_admin_1 user")
        response = self.fence.deactivate_user(username="fence_admin_1")
        assert (
            response.status_code == 200
        ), f"Expected status to be 200, but got {response.status_code}"
        logger.info("Verifying fence_admin_1 user is deactivated")
        response = self.fence.verify_authorized_username(
            verify_username="fence_admin_1"
        )
        assert (
            response.status_code == 200
        ), f"Expected status to be 200, but got {response.status_code}"
        assert not response.json()[
            "active"
        ], f"Expected user status to be False, but got {response.json()["active"]}"
        logger.info("Attempting again to deactivate fence_admin_1 user")
        response = self.fence.deactivate_user(username="fence_admin_1")
        assert (
            response.status_code == 200
        ), f"Expected status to be 200, but got {response.status_code}"
        logger.info("deactivating fence_admin_2 user which doesnt exist")
        response = self.fence.deactivate_user(username="fence_admin_2")
        assert (
            response.status_code == 404
        ), f"Expected status to be 200, but got {response.status_code}"
        msg = f"user {pytest.users["fence_admin_2"]} not found"
        assert (
            msg in response.content.decode()
        ), f"Expected {msg}, but got {response.content}"
