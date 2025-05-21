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
@pytest.mark.skipif(
    pytest.manifest.get("google", {}).get("enabled", "") != "yes",
    reason="google setup is not enabled",
)
@pytest.mark.fence
@pytest.mark.requires_fence_client
class TestOauth2:
    @classmethod
    def setup_class(cls):
        cls.fence = Fence()
        # Generate Client id and secrets
        cls.basic_test_client_id = pytest.clients["basic-test-client"]["client_id"]
        cls.basic_test_client_secret = pytest.clients["basic-test-client"][
            "client_secret"
        ]

        cls.implicit_test_client_id = pytest.clients["implicit-test-client"][
            "client_id"
        ]
        cls.implicit_test_client_secret = pytest.clients["implicit-test-client"][
            "client_secret"
        ]

    def test_authorization_code_no_user_consent_fail_code_generation(self, page: Page):
        """
        Scenario: Authorization code flow: Test that fails to generate code due to no user consent
        Steps:
            1. Generate consent code url by providing consent as 'cancel'.
            2. No consent code should be returned in url.
        """
        url = self.fence.get_consent_code(
            page=page,
            client_id=self.basic_test_client_id,
            response_type="code",
            scopes="openid+user",
            consent="cancel",
        )
        assert "code=" not in url, f"Expected code= to be missing instead got {url}"

    def test_authorization_code_successfully_code_generation(self, page: Page):
        """
        Scenario: Authorization code flow: Test that successfully generates code
        Steps:
            1. Generate consent code url.
            2. Consent code should be generated in the url.
        """
        url = self.fence.get_consent_code(
            page=page,
            client_id=self.basic_test_client_id,
            response_type="code",
            scopes="openid+user",
        )
        assert "code=" in url, f"Expected code= to be present instead got {url}"

    def test_authorization_code_no_openid_scope_fail_code_generation(self, page: Page):
        """
        Scenario: Authorization code flow: Test that fail to generate code due to not provided openid scope
        Steps:
            1. Generate consent code url by not providing openid in scope.
            2. No consent code should be returned in url.
        """
        url = self.fence.get_consent_code(
            page=page,
            client_id=self.basic_test_client_id,
            response_type="code",
            scopes="user",
            expect_code=False,
        )
        assert "code=" not in url, f"Expected code= to be missing instead got {url}"

    def test_authorization_code_wrong_response_type_fail_code_generation(
        self, page: Page
    ):
        """
        Scenario: Authorization code flow: Test that fail to generate code due to wrong response type
        Steps:
            1. Generate consent code url by providing wrong response type.
            2. No consent code should be returned in url.
        """
        url = self.fence.get_consent_code(
            page=page,
            client_id=self.basic_test_client_id,
            response_type="wrong_code",
            scopes="user",
            expect_code=False,
        )
        assert "code=" not in url, f"Expected code= to be missing instead got {url}"

    def test_authorization_code_successfully_generates_token(self, page: Page):
        """
        Scenario: Authorization code flow: Test that successfully generate tokens
        Steps:
            1. Generate consent code url.
            2. Consent code should be generated in the url.
            3. Use the code to generare the tokens.
            4. Validate the required fields are present in response.
        """
        res = self.fence.get_user_tokens_with_client(
            page=page,
            client_id=self.basic_test_client_id,
            client_secret=self.basic_test_client_secret,
            scopes="openid+user",
        )
        self.fence.assert_token_response(response=res)

    def test_authorization_code_invalid_code_fails_token_generation(self):
        """
        Scenario: Authorization code flow: Test that fails to generate tokens due to invalid code
        Steps:
            1. Generate token with authentication code as 'invalid_code'
            2. No token should be generated and status_code should be 400.
        """
        res = self.fence.get_token_with_auth_code(
            client_id=self.basic_test_client_id,
            client_secret=self.basic_test_client_secret,
            code="invalid_code",
            grant_type="authorization_code",
        )
        self.fence.assert_token_response(
            response=res, expected_status_code=400, validate_keys=False
        )

    def test_authorization_code_invalid_grant_type_fails_token_generation(
        self, page: Page
    ):
        """
        Scenario: Authorization code flow: Test that fails to generate tokens due to invalid grant type
        Steps:
            1. Generate consent code url.
            2. Consent code should be generated in the url.
            3. Generate token with grant type as 'not_supported'
            4. No token should be generated and status_code should be 400.
        """
        url = self.fence.get_consent_code(
            page=page,
            client_id=self.basic_test_client_id,
            response_type="code",
            scopes="openid+user",
        )
        assert "code=" in url, f"Expected code= to be present instead got {url}"
        code = url.split("code=")[-1]
        res = self.fence.get_token_with_auth_code(
            self.basic_test_client_id,
            self.basic_test_client_secret,
            code,
            "not_supported",
        )
        self.fence.assert_token_response(
            response=res, expected_status_code=400, validate_keys=False
        )

    def test_authorization_code_successful_token_generation_for_fence_usage(
        self, page: Page
    ):
        """
        Scenario: Authorization code flow: Test that can create an access token which can be used in fence
        Steps:
            1. Generate consent code url.
            2. Consent code should be generated in the url.
            3. Use the code to generare the tokens.
            4. Validate the required fields are present in response.
            5. Get user info from fence using the token.
            6. Validate the required fields are present in response.
        """
        res = self.fence.get_user_tokens_with_client(
            page=page,
            client_id=self.basic_test_client_id,
            client_secret=self.basic_test_client_secret,
            scopes="openid+user",
        )
        self.fence.assert_token_response(response=res)
        user_info_res = self.fence.get_user_info(
            access_token=res.json()["access_token"]
        )
        assert (
            "username" in user_info_res
        ), f"Expected username key in response but got {user_info_res}"
        assert (
            "user_id" in user_info_res
        ), f"Expected user_id key in response but got {user_info_res}"

    def test_implicit_flow_no_user_consent_fails_token_generation(self, page: Page):
        """
        Scenario: Implicit flow: Test that fails to generate tokens due to no user consent
        Steps:
            1. Generate token using implicit client with consent as 'cancel'.
            2. Validate the required fields are missing from response.
        """
        url = self.fence.get_tokens_implicit_flow(
            page=page,
            client_id=self.implicit_test_client_id,
            response_type="id_token+token",
            scopes="openid+user",
            consent="cancel",
        )
        assert (
            "token_type=Bearer" not in url
        ), f"Expected token_type=Bearer to be missing but got it in {url}"
        assert (
            "id_token=" not in url
        ), f"Expected id_token= to be missing but got it in {url}"
        assert (
            "access_token=" not in url
        ), f"Expected access_token= to be missing but got it in {url}"

    def test_implicit_flow_successfully_token_generation(self, page: Page):
        """
        Scenario: Implicit flow: Test that successfully generates id and access tokens
        Steps:
            1. Generate token using implicit client.
            2. Validate the required fields are present in response.
        """
        url = self.fence.get_tokens_implicit_flow(
            page=page,
            client_id=self.implicit_test_client_id,
            response_type="id_token+token",
            scopes="openid+user",
        )
        assert (
            "token_type=Bearer" in url
        ), f"Expected token_type=Bearer to be present but got it in {url}"
        assert (
            "id_token=" in url
        ), f"Expected id_token= to be present but got it in {url}"
        assert (
            "access_token=" in url
        ), f"Expected access_token= to be present but got it in {url}"
        assert (
            "expires_in" in url
        ), f"Expected expires_in to be present but got it in {url}"

    def test_implicit_flow_wrong_grant_types_fails_token_generation(self, page: Page):
        """
        Scenario: Implicit flow: Test that fails to generate tokens due to wrong grant types
        Steps:
            1. Generate token using implicit client with grant type as 'not_supported_grant'.
            2. Validate the required fields are missing from response.
        """
        url = self.fence.get_tokens_implicit_flow(
            page=page,
            client_id=self.implicit_test_client_id,
            response_type="not_supported_grant",
            scopes="openid+user",
            consent="ok",
            expect_token=False,
        )
        assert (
            "token_type=Bearer" not in url
        ), f"Expected token_type=Bearer to be missing but got it in {url}"
        assert (
            "id_token=" not in url
        ), f"Expected id_token= to be missing but got it in {url}"
        assert (
            "access_token=" not in url
        ), f"Expected access_token= to be missing but got it in {url}"

    def test_implicit_flow_only_id_token_successfully_token_generation(
        self, page: Page
    ):
        """
        Scenario: Implicit flow: Test that successfully generates only id token
        Steps:
            1. Generate token using implicit client with grant type as id_token only.
            2. Validate the required fields are present in response. ('access_token=' field should be missing.)
        """
        url = self.fence.get_tokens_implicit_flow(
            page=page,
            client_id=self.implicit_test_client_id,
            response_type="id_token",
            scopes="openid+user",
        )
        assert (
            "token_type=Bearer" in url
        ), f"Expected token_type=Bearer to be present but got it in {url}"
        assert (
            "id_token=" in url
        ), f"Expected id_token= to be present but got it in {url}"
        assert (
            "access_token=" not in url
        ), f"Expected access_token= to be missing but got it in {url}"  # Only access_token= should be missing
        assert (
            "expires_in" in url
        ), f"Expected expires_in to be present but got it in {url}"

    def test_implicit_flow_no_openid_scope_fails_token_generation(self, page: Page):
        """
        Scenario: Test that fails to generate tokens due to openid scope not provided
        Steps:
            1. Generate token using implicit client with scope without openid.
            2. Validate the required fields are missing from response.
        """
        url = self.fence.get_tokens_implicit_flow(
            page=page,
            client_id=self.implicit_test_client_id,
            response_type="id_token",
            scopes="user",
            consent="ok",
            expect_token=False,
        )
        assert (
            "token_type=Bearer" not in url
        ), f"Expected token_type=Bearer to be missing but got it in {url}"
        assert (
            "id_token=" not in url
        ), f"Expected id_token= to be missing but got it in {url}"
        assert (
            "access_token=" not in url
        ), f"Expected access_token= to be missing but got it in {url}"

    def test_implicit_flow_successfully_token_generation_can_be_used_by_fence(
        self, page: Page
    ):
        """
        Scenario: Implicit flow: Test that can create an access token which can be used in fence
        Steps:
            1. Generate token using implicit client.
            2. Validate the required fields are present in response.
            3. Get user info from fence using the token.
            4. Validate the required fields are present in response.
        """
        url = self.fence.get_tokens_implicit_flow(
            page=page,
            client_id=self.implicit_test_client_id,
            response_type="id_token+token",
            scopes="openid+user",
        )
        logger.info(url)
        access_token = re.findall("access_token=[a-zA-z0-9.-]*&", url)[0]
        access_token = access_token.split("=")[-1]
        access_token = access_token.replace("&", "")
        logger.info(access_token)
        user_info_res = self.fence.get_user_info(access_token=access_token)
        assert (
            "username" in user_info_res
        ), f"Expected username key in response but got {user_info_res}"
        assert (
            "user_id" in user_info_res
        ), f"Expected user_id key in response but got {user_info_res}"

    def test_authorization_flow_test_project_access(self, page: Page):
        """
        Scenario: Authorization code flow: Test project access in id token same as project access in user endpoint
        Steps:
            1. Login to home page using main_account user.
            2. Get consent code for basic-test-client.
            3. Get token using the consent code.
            4. Get projects list using id_token and access_token.
            5. Validate the same projects are present for id_token and access_token(user_endpoint)
        """
        login_page = LoginPage()
        logger.info("Logging in with mainAcct")
        login_page.go_to(page)
        login_page.login(page)

        url = self.fence.get_consent_code(
            page=page,
            client_id=self.basic_test_client_id,
            response_type="code",
            scopes="openid+user",
        )
        code = url.split("code=")[-1]
        res = self.fence.get_token_with_auth_code(
            self.basic_test_client_id,
            self.basic_test_client_secret,
            code,
            "authorization_code",
        )

        access_token = res.json()["access_token"]
        id_token = res.json()["id_token"]

        # list of projects the id token gives access to
        base64_url = id_token.split(".")[1]
        base64_str = base64_url.replace("-", "+").replace("_", "/")
        token_claims = json.loads(base64.b64decode(base64_str + "===").decode("utf-8"))
        projects_in_token = token_claims["context"]["user"]["projects"]

        # list of projects the user endpoint shows access to
        user_info_res = self.fence.get_user_info(access_token=access_token)
        projects_of_user = user_info_res["project_access"]

        # test the len of projects are same
        assert len(projects_in_token) == len(
            projects_of_user
        ), f"Length of projects list are not same.\nid_token project list: {projects_in_token}\nuser endpoint project list: {projects_of_user}"

        # test the content of projects are same
        for key, val in projects_in_token.items():
            assert (
                projects_of_user[key] == val
            ), f"Values for {key} don't match.\nid_token project list: {projects_in_token}\nuser endpoint project list: {projects_of_user}"

        login_page.logout(page)
