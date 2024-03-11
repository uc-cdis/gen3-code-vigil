import os
import pytest
import requests
import json

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Requestor(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/requestor/request"
        self.USER_ENDPOINT = f"{self.BASE_URL}/user"

    def create_request(self, data, token):
        create_req = requests.post(
            f"{self.BASE_URL}",
            json=data,
            headers={"Authorization": f"bearer {token}"},
        )
        assert (
            create_req.status_code == 201
        ), f"Expected status code 201, but got {create_req.status_code}"
        assert (
            "request_id" in create_req.json()
        ), f"Expected 'request_id' property in response data"

        request_id = create_req.json()["request_id"]
        print(f"Request ID: {request_id}")

        return request_id

    def get_request_id(self, user="dcf_integration_user"):
        id_res = requests.get(
            f"{self.USER_ENDPOINT}?policy_id=programs.jnkns.projects.jenkins_accessor",
            headers=pytest.auth_headers[user],
        )
        response_data_json = id_res.json()
        assert response_data_json, "Response data is empty"
        req_id = response_data_json[0]["request_id"]
        return req_id

    def get_request_status(self, request_id, user="main_account"):
        print(f"Checking request status ...")
        status_res = requests.get(
            f"{self.BASE_URL}/{request_id}", headers=pytest.auth_headers[user]
        )
        status_data_json = status_res.json()
        req_status = status_data_json["status"]

        return req_status

    def request_signed(self, request_id, user="main_account"):
        print(f"Updating the {request_id} to SIGNED status ...")
        requests.put(
            f"{self.BASE_URL}/{request_id}",
            json={"status": "SIGNED"},
            headers=pytest.auth_headers[user],
        )

    def request_approved(self, request_id, user="main_account"):
        print(f"Updating the {request_id} to APPROVED status ...")
        requests.put(
            f"{self.BASE_URL}/{request_id}",
            json={"status": "APPROVED"},
            headers=pytest.auth_headers[user],
        )

    def request_delete(self, request_id, user="main_account"):
        print(f"Deleting the {request_id} ...")
        response = requests.delete(
            f"{self.BASE_URL}/{request_id}", headers=pytest.auth_headers[user]
        )
        response.raise_for_status()

    def get_request_list(self, access_token):
        print(f"Getting user request list ...")
        requests.get(
            f"{self.BASE_URL}", headers={"Authorization": f"Bearer {access_token}"}
        )
