import pytest
import requests
import os

from services.fence import Fence
from services.client import Client
from services.requestor import Requestor
import utils.gen3_admin_tasks as gat

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.client_credentials
class TestClientCredentials:
    client_access_token = None
    request_id = None
    username = py

    def test_client_credentials(self):
        fence = Fence()
        requestor = Requestor()
        # Creating new OIDC client for test
        client_grant = Client(
            client_name="jenkinsClientTester",
            user_name=pytest.users["dcf_integration_user"],
            client_type="client_credentials",
            arborist_policies=None,
        )
        client_id = client_grant.id
        client_secret = client_grant.secret

        print(f"Client ID: {client_id}")
        print(f"Client Secret: {client_secret}")

        # Running usersync to sync the newly created client
        gat.run_gen3_job(pytest.namespace, "usersync")
        # TODO : wait for usersync pod to finish and completed
        client_access_token = fence.client_credentials_access_token(
            client_id, client_secret
        )

        # Creating data for request
        username = pytest.users["dcf_integration_user"]
        data = {"username": username, "policy_id": "requestor_client_credentials_test"}

        # Create new request with access_token from newly created client in previous stage
        create_req = requests.post(
            f"{requestor.self.BASE_URL}",
            data,
            fence.get_access_token_header(client_access_token),
        )
        assert (
            create_req.status_code == 201
        ), f"Expected status code 201, but got {create_req.status_code}"
        assert (
            "request_id" in create_req.json()["data"]
        ), f"Expected 'request_id' property in response data"

        self.request_id = create_req.json()["data"]["request_id"]

        # Getting the status of the request_id
        req_status = requestor.get_request_status(self.request_id)
        print(f"Status of the request is {req_status}")

        # Updating the request from DRAFT to SIGNED state and check the status of the request
        requestor.request_signed(self.request_id)
        req_status_signed = requestor.get_request_status(self.request_id)
        print(f"Status of the request is:{req_status_signed}")

        # Get the list of the user access request
        req_list = requestor.get_request_list(client_access_token)
        client_list = req_list.json()

        if len(client_list) > 0:
            req_data = [
                obj for obj in client_list if obj["request_id"] == self.request_id
            ]
            assert len(req_data) == 1


@pytest.fixture(scope="session", autouse=True)
def delete_request_id():
    yield  # Run the tests

    # Delete request_id after all tests are executed
    if TestClientCredentials.request_id:
        delete_req = requests.delete(
            f"{TestClientCredentials.requestor.self.BASE_URL}/{TestClientCredentials.request_id}",
            headers=TestClientCredentials.fence.get_access_token_header(
                TestClientCredentials.client_access_token
            ),
        )
        assert (
            delete_req.status_code == 200
        ), f"Expected status code 200, but got {delete_req.status_code}"

    revoke_policy_response = requests.delete(
        f"arborist-service/user/dcf-integration-test-0@planx-pla.net/policy/requestor_client_credentials_test"
    )
    assert (
        revoke_policy_response.status_code == 200
    ), f"Expected status code 200, but got {revoke_policy_response.status_code}"
