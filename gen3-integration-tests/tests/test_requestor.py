import json
import os

import pytest
from gen3.auth import Gen3Auth
from pages.login import LoginPage
from services.fence import Fence
from services.requestor import Requestor
from utils import logger


@pytest.mark.skipif(
    "requestor" not in pytest.deployed_services,
    reason="requestor service is not running on this environment",
)
@pytest.mark.skipif(
    "portal" not in pytest.deployed_services,
    reason="portal service is not running on this environment",
)
@pytest.mark.requestor
@pytest.mark.portal
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
            requestor.request_delete(request_id)

    def test_policy_not_in_arborist(self):
        """
        Scenario: Request for policy that does not exist in Arborist (Negative)
        Steps:
            1. Send a create request with 'random-policy' policy which does not exist in Arborist for user0
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
        random_policy = requestor.create_request_with_auth_header(
            username=req_data["username"], policy_id=req_data["policy_id"]
        )
        if random_policy is not None:
            status_code = random_policy.status_code
            logger.info(f"Status code of random policy : {status_code}")
            assert status_code == 400
        else:
            logger.info("Failed to create request with policy 'random-policy'")

    def test_request_policy_and_revoke(self, page):
        """
        Scenario: Request with access to policy followed by revoke request
        Steps:
            1. Login with main_account and check the user policy '/requestor_integration_test'
            2. Create a request with the policy with user0 and check the status
            3. Check the user policy for user0, should not have it as the request is not SIGNED
            4. Update the request to SIGNED status created in step 2
            5. Verify if the access is granted to user0
            6. Send the revoke request to revoke the access to policy
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
        # Checking the user_info for authz permissions and authz should not contain policy
        user_policy = fence.get_user_info("user0_account")
        logger.debug(f"User policy: {user_policy['authz']}")
        assert (
            "/requestor_integration_test" not in user_policy["authz"]
        ), "Authz contains policy '/requestor_integration_test'"

        # Creating new request with policy '/requestor_integration_test' and expect 201 response
        req_data = {
            "policy_id": "requestor_integration_test",
            "username": pytest.users["user0_account"],
        }
        create_resp = requestor.create_request_with_auth_header(
            username=req_data["username"], policy_id=req_data["policy_id"]
        )
        assert (
            create_resp.status_code == 201
        ), f"Create Request failed with status code : {create_resp.status_code}"
        create_resp_data = create_resp.json()
        logger.debug(f"Request Data: {json.dumps(create_resp_data, indent=4)}")
        # storing the request id to be deleted later
        if "request_id" in create_resp_data:
            request_id = create_resp_data.get("request_id")
            self.variables["request_ids"].append(request_id)
        logger.debug(f"Request ID list : {self.variables['request_ids']}")

        # Checking the user_Info for authz permissions and authz should not contain policy as the request is not in SIGNED status
        user_policy = fence.get_user_info("user0_account")
        logger.debug(f"User policy: {user_policy['authz']}")
        assert (
            "/requestor_integration_test" not in user_policy["authz"]
        ), "Authz contains policy '/requestor_integration_test'"

        # sending SIGNED request with request_id and check the user_Info which should contain policy
        requestor.request_signed(request_id)
        user_policy = fence.get_user_info("user0_account")
        assert (
            "/requestor_integration_test" in user_policy["authz"]
        ), "Authz does not contains policy '/requestor_integration_test'"

        # sending revoke request on the policy
        req_data["revoke"] = True
        logger.debug(f"Updated req_data : {req_data}")
        revoke_req = requestor.create_request_with_auth_header(
            username=req_data["username"],
            policy_id=req_data["policy_id"],
            revoke=req_data["revoke"],
        )
        assert (
            revoke_req.status_code == 201
        ), f"Create Request failed with status code : {revoke_req.status_code}"
        revoke_req_data = revoke_req.json()
        logger.debug(f"Request Data: {json.dumps(revoke_req_data, indent=4)}")
        if "request_id" in revoke_req_data:
            revoke_request_id = revoke_req_data.get("request_id")
            self.variables["request_ids"].append(revoke_request_id)
        logger.debug(f"Request ID list : {self.variables['request_ids']}")

        # Checking the user_Info for authz permissions and authz should contain policy as the revoke request is not in SIGNED status
        user_policy = fence.get_user_info("user0_account")
        logger.debug(f"User policy: {user_policy['authz']}")
        assert (
            "/requestor_integration_test" in user_policy["authz"]
        ), "Authz does not contains policy '/requestor_integration_test'"

        # sending SIGNED request with revoke_request_id and check user_info which should not contain policy
        requestor.request_signed(revoke_request_id)
        user_policy = fence.get_user_info("user0_account")
        logger.debug(f"User policy: {user_policy['authz']}")
        assert (
            "/requestor_integration_test" not in user_policy["authz"]
        ), "Authz contains policy '/requestor_integration_test'"

    def test_revoke_request_no_access(self, page):
        """
        Scenario: Request to revoke for policy that exists in Arborist but user does not have access to - (Negative)
        Steps:
            1. Login with main_account and check the user policy '/requestor_integration_test' in user_info
            2. Send a revoke request to policy '/requestor_integration_test' to which user0 has no access
            3. Request status code = 400
        """
        login_page = LoginPage()
        fence = Fence()
        requestor = Requestor()
        login_page.go_to(page)
        login_page.login(page)
        # Checking the user_info for authz permissions and authz should not contain policy
        user_policy = fence.get_user_info("user0_account")
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
        revoke_req = requestor.create_request_with_auth_header(
            username=req_data["username"],
            policy_id=req_data["policy_id"],
            revoke=req_data["revoke"],
        )
        if revoke_req is not None:
            status_code = revoke_req.status_code
            logger.info(f"Status code of revoke policy : {status_code}")
            assert status_code == 400
        else:
            logger.info(
                "Failed to create revoke request with policy '/requestor_integration_test'"
            )

    def test_revoke_signed_request(self, page):
        """
        Scenario: Request to access policy with SIGNED status and revoke it later
        Steps:
            1. Login with main_account and check the user policy '/requestor_integration_test' in user_info
            2. Send a create request for user 0 with request_status = SIGNED
            3. Check the user policy '/requestor_integration_test' is present in user0 user_info
            4. Send a revoke request and check if the user policy '/requestor_integration_test' is not in user 0 user_info
        """
        login_page = LoginPage()
        fence = Fence()
        requestor = Requestor()
        request_id = None
        revoke_request_id = None
        login_page.go_to(page)
        login_page.login(page)
        # Checking the user_info for authz permissions and authz should not contain policy
        user_policy = fence.get_user_info("user0_account")
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
        signed_req = requestor.create_request_with_auth_header(
            username=req_data["username"],
            policy_id=req_data["policy_id"],
            request_status=req_data["status"],
        )
        assert (
            signed_req.status_code == 201
        ), f"Create Request failed with status code : {signed_req.status_code}"
        signed_req_data = signed_req.json()
        logger.debug(f"Request Data: {json.dumps(signed_req_data, indent=4)}")
        if "request_id" in signed_req_data:
            request_id = signed_req_data.get("request_id")
            self.variables["request_ids"].append(request_id)
        logger.debug(f"Request ID list : {self.variables['request_ids']}")

        # Checking the user_info for authz permissions and authz should contain policy
        user_policy = fence.get_user_info("user0_account")
        assert (
            "/requestor_integration_test" in user_policy["authz"]
        ), "Authz does not contains policy '/requestor_integration_test'"

        # sending revoke request
        req_data["revoke"] = True
        logger.debug(f"Updated req_data : {req_data}")
        revoke_req = requestor.create_request_with_auth_header(
            username=req_data["username"],
            policy_id=req_data["policy_id"],
            revoke=req_data["revoke"],
            request_status=req_data["status"],
        )
        assert (
            revoke_req.status_code == 201
        ), f"Create Request failed with status code : {revoke_req.status_code}"
        revoke_req_data = revoke_req.json()
        logger.debug(f"Request Data: {json.dumps(revoke_req_data, indent=4)}")
        if "request_id" in revoke_req_data:
            revoke_request_id = revoke_req_data.get("request_id")
            self.variables["request_ids"].append(revoke_request_id)
        logger.debug(f"Request ID list : {self.variables['request_ids']}")

        # Checking the user_info for authz permissions and authz should not contain policy
        user_policy = fence.get_user_info("user0_account")
        logger.debug(f"User policy: {user_policy['authz']}")
        assert (
            "/requestor_integration_test" not in user_policy["authz"]
        ), "Authz contains policy '/requestor_integration_test'"

    def test_request_resource_path_and_role_ids(self, page):
        """
        Scenario: Request to access for resource_paths and role_ids wth SIGNED status and revoke it later
        Steps:
            1. Login with main_account and check the user policy '/requestor_integration_test' in user_info
            2. Send a create request for user0 with resource_paths and role_ids with SIGNED status
            3. Send a revoke request with policy_id from step 2 with SIGNED status
            4. And verify that the user policy '/requestor_integration_test' is not present in user_info
        """
        login_page = LoginPage()
        fence = Fence()
        requestor = Requestor()
        request_id = None
        revoke_request_id = None
        login_page.go_to(page)
        login_page.login(page)
        # Checking the user_info for authz permissions and authz should not contain policy
        user_policy = fence.get_user_info("user0_account")
        logger.debug(f"User policy: {user_policy['authz']}")
        assert (
            "/requestor_integration_test" not in user_policy["authz"]
        ), "Authz contains policy '/requestor_integration_test'"

        # sending a create request with resource_path and role id
        req_data = {
            "username": pytest.users["user0_account"],
            "resource_paths": ["/requestor_integration_test"],
            "role_ids": ["workspace_user", "mds_user"],
            "status": "SIGNED",
        }

        signed_req = requestor.create_request_with_auth_header(
            username=req_data["username"],
            resource_paths=req_data["resource_paths"],
            role_ids=req_data["role_ids"],
            request_status=req_data["status"],
        )
        assert (
            signed_req.status_code == 201
        ), f"Create Request failed with status code : {signed_req.status_code}"
        signed_req_data = signed_req.json()
        logger.debug(f"Request Data: {json.dumps(signed_req_data, indent=4)}")
        if "request_id" in signed_req_data:
            request_id = signed_req_data.get("request_id")
            self.variables["request_ids"].append(request_id)
        logger.debug(f"Request ID list : {self.variables['request_ids']}")
        # storing the policy_id for revoke request
        policy = signed_req_data.get("policy_id")

        # Checking the user_info for authz permissions and authz should contain policy
        user_policy = fence.get_user_info("user0_account")
        assert (
            "/requestor_integration_test" in user_policy["authz"]
        ), "Authz does not contains policy '/requestor_integration_test'"

        # sending revoke request
        revoke_data = {
            "username": pytest.users["user0_account"],
            "revoke": True,
            "policy_id": policy,
            "status": "SIGNED",
        }
        revoke_req = requestor.create_request_with_auth_header(
            username=revoke_data["username"],
            policy_id=revoke_data["policy_id"],
            revoke=revoke_data["revoke"],
            request_status=revoke_data["status"],
        )
        assert (
            revoke_req.status_code == 201
        ), f"Revoke Request failed with status code : {revoke_req.status_code}"
        revoke_req_data = revoke_req.json()
        logger.debug(f"Request Data: {json.dumps(revoke_req_data, indent=4)}")
        if "request_id" in revoke_req_data:
            revoke_request_id = revoke_req_data.get("request_id")
            self.variables["request_ids"].append(revoke_request_id)
        logger.debug(f"Request ID list : {self.variables['request_ids']}")

        # Checking the user_info for authz permissions and authz should not contain policy
        user_policy = fence.get_user_info("user0_account")
        logger.debug(f"User policy: {user_policy['authz']}")
        assert (
            "/requestor_integration_test" not in user_policy["authz"]
        ), "Authz contains policy '/requestor_integration_test'"
