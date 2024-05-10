import pytest
import os
import json

from gen3.auth import Gen3Auth
from services.fence import Fence
from pages.login import LoginPage
from services.requestor import Requestor

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.requestor
class TestRequestor:
    variables = {}

    @classmethod
    def setup_class(cls):
        cls.variables["request_ids"] = []

    @classmethod
    def teardown_class(cls):
        """Delete all the requests from requestor db after the test is executed"""
        requestor = Requestor()
        for request_id in cls.variables["request_ids"]:
            requestor.delete(request_id)

    def test_policy_not_in_arborist(self):
        """
        Scenario: Request for policy that does not exist in Arborist (Negative)
        Steps:
            1. Send a request with 'random-policy' policy which does not exist in Arborist
            2. Expected 400 status code as response
        """
        requestor = Requestor()
        req_data = {
            "policy_id": "random-policy",
            "username": pytest.users["user0_account"],
        }
        logger.info(
            "Creating request with policy 'random-policy' which does not exist in Arborist"
        )
        random_policy = requestor.create_request_with_authHeader(
            username=req_data["username"], policy_id=req_data["policy_id"]
        )
        if random_policy is not None:
            status_code = random_policy.get("status_code")
            logger.info(f"Status code of random policy : {status_code}")
            assert status_code == 400
        else:
            logger.info("Failed to create request with policy 'random-policy'")

    def test_request_policy_and_revoke(self, page):
        """
        Scenario: Request with access to policy followed by revoke request
        Steps:
            1. Login with main_account and check the user policy '/requestor_integration_test'
            2. Create a request with the policy and check the status
            3. Check the user policy, should not have it as the request is not SIGNED
            4. Update the request to SIGNED status
            5. Verify if the access is granted to user
            6. Send the revoke request
            7. Check if the access is revoke, should not have revoked the access as revoke request is not signed
            8. Update the request to SIGNED status and check if access is revoked
        """
        login_page = LoginPage()
        fence = Fence()
        requestor = Requestor()
        request_id = None
        revoke_request_id = None
        login_page.go_to(page)
        login_page.login(page)
        # Checking the userInfo for authz permissions and authz should not contain policy
        # logger.info(f"Auth Headers: {pytest.auth_headers['main_account']}")
        user_policy = fence.getUserInfo()
        logger.debug(f"User policy: {user_policy['authz']}")
        assert (
            "/requestor_integration_test" not in user_policy["authz"]
        ), "Authz contains policy '/requestor_integration_test'"

        # Creating new request with policy '/requestor_integration_test'
        req_data = {
            "policy_id": "requestor_integration_test",
            "username": pytest.users["user0_account"],
        }
        create_resp = requestor.create_request_with_authHeader(
            username=req_data["username"], policy_id=req_data["policy_id"]
        )
        logger.info(f"Request Data: {json.dumps(create_resp, indent=4)}")
        status_code = create_resp.get("status_code")
        assert (
            status_code == 201
        ), f"Create Request failed with status code : {status_code}"
        if status_code == 201:
            request_id = create_resp.get("request_id")
            self.variables["request_ids"].append(request_id)
        logger.info(f"Request ID list : {TestRequestor.variables['request_ids']}")

        # Checking the userInfo for authz permissions and authz should not contain policy as the request is not in SIGNED status
        user_policy = fence.getUserInfo()
        logger.debug(f"User policy: {user_policy['authz']}")
        assert (
            "/requestor_integration_test" not in user_policy["authz"]
        ), "Authz contains policy '/requestor_integration_test'"

        # sending SIGNED request with request_id and check the userInfo which should contain policy
        requestor.request_signed(request_id)
        user_policy = fence.getUserInfo()
        assert (
            "/requestor_integration_test" in user_policy["authz"]
        ), "Authz does not contains policy '/requestor_integration_test'"

        # sending revoke request on the policy
        req_data["revoke"] = True
        logger.debug(f"{req_data}")
        revoke_req = requestor.create_request_with_authHeader(
            username=req_data["username"],
            policy_id=req_data["policy_id"],
            revoke=req_data["revoke"],
        )
        status_code = revoke_req.get("status_code")
        assert (
            status_code == 201
        ), f"Create Request failed with status code : {status_code}"
        if status_code == 201:
            revoke_request_id = revoke_req.get("request_id")
            self.variables["request_ids"].append(revoke_request_id)
        logger.info(f"Request ID list : {TestRequestor.variables['request_ids']}")

        # Checking the userInfo for authz permissions and authz should contain policy as the revoke request is not in SIGNED status
        user_policy = fence.getUserInfo()
        logger.debug(f"User policy: {user_policy['authz']}")
        assert (
            "/requestor_integration_test" in user_policy["authz"]
        ), "Authz does not contains policy '/requestor_integration_test'"

        # sending SIGNED request with revoke_request_id and check userinfo which should not contain policy
        requestor.request_signed(revoke_request_id)
        user_policy = fence.getUserInfo()
        logger.debug(f"User policy: {user_policy['authz']}")
        assert (
            "/requestor_integration_test" not in user_policy["authz"]
        ), "Authz contains policy '/requestor_integration_test'"

    def test_revoke_request_no_access(self, page):
        """
        Scenario: Request to revoke for policy that exists in Arborist but user does not have access to -(Negative)
        Steps:
            1. Login with main_account and check the user policy '/requestor_integration_test' in userinfo
            2. Send a revoke request to policy '/requestor_integration_test'
            3. Request status code = 400
        """
        login_page = LoginPage()
        fence = Fence()
        requestor = Requestor()
        login_page.go_to(page)
        login_page.login(page)
        # Checking the userInfo for authz permissions and authz should not contain policy
        user_policy = fence.getUserInfo()
        logger.debug(f"User policy: {user_policy['authz']}")
        assert (
            "/requestor_integration_test" not in user_policy["authz"]
        ), "Authz contains policy '/requestor_integration_test'"

        # Sending revoke request
        req_data = {
            "policy_id": "requestor_integration_test",
            "username": pytest.users["user0_account"],
            "revoke": True,
        }
        revoke_req = requestor.create_request_with_authHeader(
            username=req_data["username"],
            policy_id=req_data["policy_id"],
            revoke=req_data["revoke"],
        )
        if revoke_req is not None:
            status_code = revoke_req.get("status_code")
            logger.info(f"Status code of random policy : {status_code}")
            assert status_code == 400
        else:
            logger.info("Failed to create request with policy 'random-policy'")

    def test_revoke_signed_request(self, page):
        """
        Scenario: Request to access policy with SIGNED status and revoke it later
        Steps:
            1. Login with main_account and check the user policy '/requestor_integration_test' in userinfo
            2. Send a create request with request_status = SIGNED
            3. Check the user policy '/requestor_integration_test' is present in userinfo
            4. Send a revoke request and check if the user policy '/requestor_integration_test' is not in userinfo
        """
        login_page = LoginPage()
        fence = Fence()
        requestor = Requestor()
        request_id = None
        revoke_request_id = None
        login_page.go_to(page)
        login_page.login(page)
        # Checking the userInfo for authz permissions and authz should not contain policy
        user_policy = fence.getUserInfo()
        logger.debug(f"User policy: {user_policy['authz']}")
        assert (
            "/requestor_integration_test" not in user_policy["authz"]
        ), "Authz contains policy '/requestor_integration_test'"

        # sending create request with SIGNED status
        req_data = {
            "policy_id": "requestor_integration_test",
            "username": pytest.users["user0_account"],
            "status": "SIGNED",
        }
        signed_req = requestor.create_request_with_authHeader(
            username=req_data["username"],
            policy_id=req_data["policy_id"],
            request_status=req_data["status"],
        )
        status_code = signed_req.get("status_code")
        assert (
            status_code == 201
        ), f"Create Request failed with status code : {status_code}"
        if status_code == 201:
            request_id = signed_req.get("request_id")
            self.variables["request_ids"].append(request_id)
        logger.info(f"Request ID list : {TestRequestor.variables['request_ids']}")

        # Checking the userInfo for authz permissions and authz should contain policy
        user_policy = fence.getUserInfo()
        assert (
            "/requestor_integration_test" in user_policy["authz"]
        ), "Authz does not contains policy '/requestor_integration_test'"

        # sending revoke request
        req_data["revoke"] = True
        logger.debug(f"{req_data}")
        revoke_req = requestor.create_request_with_authHeader(
            username=req_data["username"],
            policy_id=req_data["policy_id"],
            revoke=req_data["revoke"],
            request_status=req_data["status"],
        )
        status_code = revoke_req.get("status_code")
        assert (
            status_code == 201
        ), f"Create Request failed with status code : {status_code}"
        if status_code == 201:
            revoke_request_id = revoke_req.get("request_id")
            self.variables["request_ids"].append(revoke_request_id)
        logger.info(f"Request ID list : {TestRequestor.variables['request_ids']}")

        # Checking the userInfo for authz permissions and authz should not contain policy
        user_policy = fence.getUserInfo()
        logger.debug(f"User policy: {user_policy['authz']}")
        assert (
            "/requestor_integration_test" not in user_policy["authz"]
        ), "Authz contains policy '/requestor_integration_test'"

    def test_request_resource_path_and_role_ids(self, page):
        """
        Scenario: Request to access for resource_paths and role_ids wth SIGNED status and revoke it later
        Steps:
            1. Login with main_account and check the user policy '/requestor_integration_test' in userinfo
            2. Send a create request with resource_paths and role_ids with SIGNED status
            3. Send a revoke request with policy_id from step 2 with SIGNED status
            4. And verify that the user policy '/requestor_integration_test' is not present in userinfo
        """
        login_page = LoginPage()
        fence = Fence()
        requestor = Requestor()
        request_id = None
        revoke_request_id = None
        login_page.go_to(page)
        login_page.login(page)
        # Checking the userInfo for authz permissions and authz should not contain policy
        user_policy = fence.getUserInfo()
        logger.debug(f"User policy: {user_policy['authz']}")
        assert (
            "/requestor_integration_test" not in user_policy["authz"]
        ), "Authz contains policy '/requestor_integration_test'"

        # sending a create request with resource_path and role id
        req_data = {
            "policy_id": "requestor_integration_test",
            "username": pytest.users["user0_account"],
            "resource_path": ["/requestor_integration_test"],
            "role_id": ["workspace_user", "mds_user"],
            "status": "SIGNED",
        }

        signed_req = requestor.create_request_with_authHeader(
            username=req_data["username"],
            policy_id=req_data["policy_id"],
            resource_paths=req_data["resource_path"],
            role_ids=req_data["role_id"],
            request_status=req_data["status"],
        )
        status_code = signed_req.get("status_code")
        assert (
            status_code == 201
        ), f"Create Request failed with status code : {status_code}"
        if status_code == 201:
            request_id = signed_req.get("request_id")
            self.variables["request_ids"].append(request_id)
        logger.info(f"Request ID list : {TestRequestor.variables['request_ids']}")

        # storing the policy_id for revoke request
        policy_id = signed_req.get("policy_id")

        # Checking the userInfo for authz permissions and authz should contain policy
        user_policy = fence.getUserInfo()
        assert (
            "/requestor_integration_test" in user_policy["authz"]
        ), "Authz does not contains policy '/requestor_integration_test'"

        # sending revoke request
        revoke_data = {
            "username": pytest.users["user0_account"],
            "revoke": True,
            "policy_id": policy_id,
            "status": "SINGED",
        }
        revoke_req = requestor.create_request_with_authHeader(
            username=req_data["username"],
            policy_id=req_data["policy_id"],
            revoke=req_data["revoke"],
            request_status=req_data["status"],
        )
        status_code = revoke_req.get("status_code")
        assert (
            status_code == 201
        ), f"Create Request failed with status code : {status_code}"
        if status_code == 201:
            revoke_request_id = revoke_req.get("request_id")
            self.variables["request_ids"].append(revoke_request_id)
        logger.info(f"Request ID list : {TestRequestor.variables['request_ids']}")

        # Checking the userInfo for authz permissions and authz should not contain policy
        user_policy = fence.getUserInfo()
        logger.debug(f"User policy: {user_policy['authz']}")
        assert (
            "/requestor_integration_test" not in user_policy["authz"]
        ), "Authz contains policy '/requestor_integration_test'"
