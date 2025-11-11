"""
RAS AuthN
"""

import os

import pytest
from pages.login import LoginPage
from playwright.sync_api import Page
from services.fence import Fence
from services.ras import RAS
from utils import gen3_admin_tasks as gat


@pytest.mark.skipif(
    "fence" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.skipif(
    pytest.manifest.get("global", {}).get("frontend_root", "") == "gen3ff",
    reason="frontend_root is set to gen3ff",
)
@pytest.mark.skipif(
    gat.get_portal_config().get("components", {}).get("appName", "")
    == "VA Data Commons",
    reason="Skipping RAS Auth N tests for VA env",
)
@pytest.mark.skipif(
    "nightly-build" not in pytest.hostname,
    reason="Test is being run on Helm and would run only on nightly-build",
)
@pytest.mark.skipif(
    "portal" not in pytest.deployed_services
    and "frontend-framework" not in pytest.deployed_services,
    reason="Both portal and frontend-framework services are not running on this environment",
)
@pytest.mark.fence
@pytest.mark.ras
@pytest.mark.requires_fence_client
class TestRasAuthN:
    @classmethod
    def setup_class(cls):
        cls.fence = Fence()
        cls.ras = RAS()
        cls.login_page = LoginPage()
        cls.env_vars = [
            "CI_TEST_RAS_EMAIL",
            "CI_TEST_RAS_PASSWORD",
            "CI_TEST_RAS_2_EMAIL",
            "CI_TEST_RAS_2_PASSWORD",
        ]
        # Validate creds required for test are defined as env variable
        cls.ras.validate_creds(test_creds=cls.env_vars)

    def test_ras_client_with_scope(self, page: Page):
        """
        Scenario: RAS User 1 () with scope ga4gh_passport_v1 permission
        Steps:
            1. Get client_id and client_secret for RAS User 1
            2. Use client_id and client_secret, get auth_code and tokens with OIDC bootstrapping
            3. With access_token, check the use permissions to have ga4gh_passport_v1
            4. Refresh access_token with refresh_token with OIDC bootstrapping
            5. Check access_token, refresh_token and id_token is returned in refresh_token response
        """
        # Get client_id and client_secret with ga4gh_passport_v1 scope from test_data/fence_clients list
        client_id = pytest.clients["ras-test-client"]["client_id"]
        client_secret = pytest.clients["ras-test-client"]["client_secret"]
        # Login with RAS user 128, click GRANT button on /authorize/consent url
        # and click on 'Yes. I authorize' button
        # Get code from the url
        scope = "openid user data google_credentials ga4gh_passport_v1"
        username = os.environ["CI_TEST_RAS_EMAIL"].split("@")[0]
        password = os.environ["CI_TEST_RAS_PASSWORD"]
        email = os.environ["CI_TEST_RAS_EMAIL"]
        token = self.ras.get_tokens(
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
            username=username,
            password=password,
            page=page,
            email=email,
        )

        # Check if access_token, refresh_token and id_token in token response
        assert (
            "access_token" in token
        ), "access_token is missing from the refresh_token response."
        assert (
            "refresh_token" in token
        ), "refresh_token is missing from the refresh_token response."
        assert (
            "id_token" in token
        ), "id_token is missing from the refresh_token response."

        # Extracting access_token and refresh token from the token response
        access_token = token.get("access_token")
        refresh_token = token.get("refresh_token")
        # Check user_info to have ga4gh_passport_v1 permissions
        user_permission = self.fence.get_user_info(access_token=access_token)
        assert (
            "ga4gh_passport_v1" in user_permission
        ), "User does not have 'ga4gh_passport_v1' permission in /user/user"
        # Using refresh_token to refresh the access token
        token_refresh_response = self.ras.get_token_from_refresh_token(
            refresh_token=refresh_token,
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
        )
        # Check if access_token, refresh_token and id_token in token refresh response
        assert (
            "access_token" in token_refresh_response
        ), "access_token is missing from the refresh_token response."
        assert (
            "refresh_token" in token_refresh_response
        ), "refresh_token is missing from the refresh_token response."
        assert (
            "id_token" in token_refresh_response
        ), "id_token is missing from the refresh_token response."

        # Check user_info after refreshing the access token to have ga4gh_passport_v1 permissions
        user_permission = self.fence.get_user_info(access_token=access_token)
        assert (
            "ga4gh_passport_v1" in user_permission
        ), "User does not have 'ga4gh_passport_v1' permission in /user/user"
        self.login_page.logout(page=page)

    def test_ras_client_without_scope(self, page: Page):
        """
        Scenario: RAS User 2 without scope ga4gh_passport_v1 permission
        Steps:
            1. Get client_id and client_secret for RAS User 2
            2. Use client_id and client_secret, get auth_code and tokens with OIDC bootstrapping
            3. With access_token, check the use permissions to have ga4gh_passport_v1
        """
        # Get client_id and client_secret with ga4gh_passport_v1 scope from test_data/fence_clients list
        client_id = pytest.clients["ras-test-client2"]["client_id"]
        client_secret = pytest.clients["ras-test-client2"]["client_secret"]
        # Login with RAS user 129, click GRANT button on /authorize/consent url
        # and click on 'Yes. I authorize' button
        # Get code from the url
        scope = "openid user data google_credentials"
        username = os.environ["CI_TEST_RAS_2_EMAIL"].split("@")[0]
        password = os.environ["CI_TEST_RAS_2_PASSWORD"]
        email = os.environ["CI_TEST_RAS_2_EMAIL"]
        token = self.ras.get_tokens(
            client_id=client_id,
            client_secret=client_secret,
            scope=scope,
            username=username,
            password=password,
            page=page,
            email=email,
        )

        # Check if access_token, refresh_token and id_token in token response
        assert (
            "access_token" in token
        ), "access_token is missing from the refresh_token response."
        assert (
            "refresh_token" in token
        ), "refresh_token is missing from the refresh_token response."
        assert (
            "id_token" in token
        ), "id_token is missing from the refresh_token response."

        # Extracting access_token and refresh token from the token response
        access_token = token.get("access_token")
        # Check user_info
        user_permission = self.fence.get_user_info(access_token=access_token)
        assert (
            "ga4gh_passport_v1" not in user_permission
        ), "User have 'ga4gh_passport_v1' permission in /user/user"
        self.login_page.logout(page=page)

    def test_provide_invalid_credentials_NIH_login_page(self, page: Page):
        """
        Scenario: Provide invalid credentials in NIH Login page
        Steps:
            1. Create a RAS test client and get its client_id.
            2. Use the RAS Login url generated using the client_id.
            3. Provide an invalid password to login.
            4. Verify 'Access Denied' is visible on page.
        NOTE : This test requires CI_TEST_RAS_ID & CI_TEST_RAS_PASSWORD
        secrets to be configured with RAS credentials
        """
        # Confirm CI_TEST_RAS_EMAIL and CI_TEST_RAS_PASSWORD are present in env
        assert "CI_TEST_RAS_EMAIL" in os.environ, "CI_TEST_RAS_EMAIL not found"
        assert "CI_TEST_RAS_PASSWORD" in os.environ, "CI_TEST_RAS_PASSWORD not found"

        self.login_page.go_to(page)
        self.login_page.ras_login(
            page,
            username=os.environ["CI_TEST_RAS_EMAIL"].split("@")[0],
            password="THIS_IS_AN_INVALID_PASSWORD_FOR_USER_1",
        )
        html_content = page.content()
        assert (
            "Access Denied" in html_content
        ), f"Expected Access Denied but got {html_content}"
