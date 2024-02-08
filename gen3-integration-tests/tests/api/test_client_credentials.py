import pytest
import requests
import os

from gen3.auth import Gen3Auth
from services.requestor import Requestor
from services.fence import Fence
import utils.gen3_admin_tasks as gat

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.client_credentials
class TestClientCredentials:
    client_access_token = None
    request_id = None
    username = pytest.users["dcf_integration_user"]
    policy = "requestor_client_credentials_test"

    def test_client_credentials(self):
        """
        1. Create a client in Fence Db with grant_type=client_credential and run usersync
        2. Create a client_access_token from the client_id and client_secret
        3. Create a new Requestor request with client_access_token
        4. Update the request to SIGNED status
        """
        requestor = Requestor()
        fence = Fence()

        # creating a new client for the test
        client = gat.create_client("")

        # Running usersync to sync the newly created client
        gat.run_gen3_job(pytest.namespace, "usersync")
        # TODO : wait for usersync pod to finish and completed
        client_access_token = Gen3Auth(
            endpoint=pytest.root_url,
            client_credentials=(client_id, client_secret),
            scope="openid user",
        )

        # Creating data for request
        data = {"username": self.username, "policy_id": self.policy}

        # Create new request with access_token from newly created client in previous stage
        create_req = requests.post(
            f"{requestor.self.BASE_URL}",
            data,
            header={"Authorization": f"bearer {client_access_token}"},
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
        req_list = requestor.get_request_list(auth)
        client_list = req_list.json()

        if len(client_list) > 0:
            req_data = [
                obj for obj in client_list if obj["request_id"] == self.request_id
            ]
            assert len(req_data) == 1


@pytest.fixture(scope="session", autouse=True)
def delete_and_revoke():
    yield  # Run the tests

    # Delete request_id after all tests are executed
    if TestClientCredentials.request_id:
        delete_req = (
            requests.delete(
                f"{TestClientCredentials.requestor.self.BASE_URL}/{TestClientCredentials.request_id}",
                headers={
                    "Authorization": f"bearer {TestClientCredentials.client_access_token}"
                },
            ),
        )
        assert (
            delete_req.status_code == 200
        ), f"Expected status code 200, but got {delete_req.status_code}"

    # Revoke arborist policy for the user
    revoke_policy_response = requests.delete(
        f"http://arborist-service/user/{TestClientCredentials.username}/policy/{TestClientCredentials.policy}"
    )
    assert (
        revoke_policy_response.status_code == 200
    ), f"Expected status code 200, but got {revoke_policy_response.status_code}"

    # Delete the client from the fence db
    delete_client = gat.delete_client
