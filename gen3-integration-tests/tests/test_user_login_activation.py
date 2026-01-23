"""
User Login Activation
"""

import pytest
import utils.gen3_admin_tasks as gat
from pages.login import LoginPage
from playwright.sync_api import Page, expect
from services.fence import Fence
from utils import logger


@pytest.mark.skipif(
    "fence" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.fence
class TestUserLoginActivation:
    @classmethod
    def setup_class(cls):
        cls.login_page = LoginPage()
        cls.fence = Fence()

        # Add new user to pytest.users
        pytest.users["authorized_user_1"] = "authorized-user-1@example.org"
        pytest.users["authorized_user_2"] = "authorized-user-2@example.org"

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
        logger.info("deactivating authorized_user_1 user")
        response = self.fence.deactivate_user(username="authorized_user_1")
        assert (
            response.status_code == 200
        ), f"Expected status to be 200, but got {response.status_code}"
        self.login_page.go_to(page)
        self.login_page.login(
            page, user="authorized_user_1", validate_username_locator=False
        )
        expect(
            page.get_by_text("User is known but not authorized/activated in the system")
        ).to_be_visible()
        gat.activate_fence_user(username="authorized_user_1")
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
        self.login_page.go_to(page)
        self.login_page.login(page, user="authorized_user_1")
        self.login_page.logout(page)

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
