import os
import pytest
import requests
import json

from gen3.auth import Gen3Auth
from services.fence import Fence

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Requestor(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/requestor/request"
        self.USER_ENDPOINT = f"{self.BASE_URL}/user"
        self.REVOKE_URL = f"{self.BASE_URL}?revoke"

    def create_request_with_clientToken(self, data, client_token):
        """Create a new request in requestor with client token"""
        create_req = requests.post(
            f"{self.BASE_URL}",
            json=data,
            headers={"Authorization": f"bearer {client_token}"},
        )
        logger.debug(json.dumps(create_req.json(), indent=4))
        assert (
            create_req.status_code == 201
        ), f"Expected status code 201, but got {create_req.status_code}"
        assert (
            "request_id" in create_req.json()
        ), f"Expected 'request_id' property in response data"

        request_id = create_req.json()["request_id"]
        logger.debug(f"Request ID: {request_id}")

        return request_id

    def create_request_with_authHeader(
        self,
        user: str = "main_account",
        username: str = None,
        policy_id: str = None,
        resource_paths: list = None,
        role_ids: list = None,
        revoke: bool = False,
        request_status: str = None,
    ):
        """Create a new request in requestor with auth_headers"""
        data = {}
        gen3auth = Gen3Auth(refresh_token=pytest.api_keys[user])
        # if policy_id is argument
        if policy_id and not (resource_paths or role_ids):
            logger.info(
                f"Creating request with policy_id : {policy_id} with revoke {revoke}"
            )
            data = {
                "policy_id": policy_id,
                "username": username,
            }
        # if resource_paths and role_ids is arguments
        elif resource_paths and role_ids and not policy_id:
            logger.info(
                f"Creating request for resource_paths : {resource_paths} and roles_ids : {role_ids} with revoke {revoke}"
            )
            data = {
                "username": username,
                "resource_paths": resource_paths,
                "role_ids": role_ids,
            }
        else:
            logger.info(
                f"Incorrect args in create request: must have policyID or resourcePaths+roleIds"
            )
            return None
        # if request_status is argument
        if request_status:
            data["status"] = request_status
        # if revoke=true using revoke url else using base_url
        endpoint = f"{self.REVOKE_URL}" if revoke else f"{self.BASE_URL}"
        # send post request
        create_req = requests.post(
            endpoint,
            json=data,
            headers={"Authorization": f"bearer {gen3auth.get_access_token()}"},
        )
        logger.info(f"### {create_req.text}")
        return create_req

    def get_request_id(self, policy: str, user: str):
        """Gets the request_id for the user"""
        id_res = requests.get(
            f"{self.USER_ENDPOINT}?policy_id={policy}",
            headers=pytest.auth_headers[user],
        )
        response_data_json = id_res.json()
        assert response_data_json, "Response data is empty"
        req_id = response_data_json[0]["request_id"]
        return req_id

    def get_request_status(self, request_id: str, user: str = "main_account"):
        """Gets the request_status for the user's request_id in requestor"""
        status_res = requests.get(
            f"{self.BASE_URL}/{request_id}", headers=pytest.auth_headers[user]
        )
        status_data_json = status_res.json()
        req_status = status_data_json["status"]

        return req_status

    def request_signed(self, request_id: str, user: str = "main_account"):
        """Updates the request to SIGNED status"""
        logger.info(f"Updating the {request_id} to SIGNED status ...")
        requests.put(
            f"{self.BASE_URL}/{request_id}",
            json={"status": "SIGNED"},
            headers=pytest.auth_headers[user],
        )

    def request_approved(self, request_id: str, user: str = "main_account"):
        """Updates the request to APPROVED status"""
        logger.info(f"Updating the {request_id} to APPROVED status ...")
        requests.put(
            f"{self.BASE_URL}/{request_id}",
            json={"status": "APPROVED"},
            headers=pytest.auth_headers[user],
        )

    def request_delete(self, request_id: str, user: str = "main_account"):
        """Deletes the request fro requestor"""
        logger.info(f"Deleting the {request_id} ...")
        response = requests.delete(
            f"{self.BASE_URL}/{request_id}", headers=pytest.auth_headers[user]
        )
        response.raise_for_status()

    def get_request_list(self, user: str):
        """Gets te list of requests for the user"""
        gen3auth = Gen3Auth(refresh_token=pytest.api_keys[user])
        logger.info(f"Getting user request list ...")
        requests.get(
            f"{self.BASE_URL}",
            headers={"Authorization": f"Bearer {gen3auth.get_access_token()}"},
        )

    # TODO : use Gen3Auth.curl to send requests
    # def create_request(self, client_id, client_secret):
    #     """Create a new request in requestor"""
    #     auth = Gen3Auth(
    #         endpoint=pytest.root_url,
    #         client_credentials=(client_id, client_secret),
    #     )
    #     logger.info(f"Client Access Token: {auth._access_token}")
    #     # Create new request with access_token from newly created client in previous stage
    #     create_req = auth.curl(
    #         self.BASE_URL,
    #         request="POST",
    #         data="@client_cred_data.json",
    #     )
    #     logger.debug(json.dumps(create_req.json(), indent=4))
    #     assert (
    #         create_req.status_code == 201
    #     ), f"Expected status code 201, but got {create_req.status_code}"
    #     assert (
    #         "request_id" in create_req.json()
    #     ), f"Expected 'request_id' property in response data"

    #     request_id = create_req.json()["request_id"]
    #     logger.debug(f"Request ID: {request_id}")

    #     return request_id
