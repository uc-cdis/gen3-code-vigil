import pytest
import requests
import os
import json

from gen3.auth import Gen3Auth
from services.requestor import Requestor
from services.fence import Fence
import utils.gen3_admin_tasks as gat

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.client_credentials
@pytest.mark.fence
@pytest.mark.requestor
class TestClientCredentials:
    def test_client_credentials(self):
        """
        1. Create a client in Fence Db with grant_type=client_credential and run usersync
        2. Create a client_access_token from the client_id and client_secret
        3. Create a new Requestor request with client_access_token
        4. Update the request to SIGNED status
        """
        client_access_token = None
        request_id = None
        username = pytest.users["user0_account"]
        policy = "requestor_client_credentials_test"
        requestor = Requestor()

        # creating a new client for the test
        client_creds = gat.create_fence_client(
            pytest.namespace,
            "jenkinsClientTester",
            username,
            "client_credentials",
        )

        # access the client_creds.txt and retrieving the client_creds
        credsFile = client_creds["client_creds.txt"].splitlines()
        if len(credsFile) < 2:
            raise Exception(
                "Client credentials file does not contain expected data format (2 lines)"
            )

        # assigning first line to client_id
        # and assigning second line to client_secret
        client_id = credsFile[0]
        client_secret = credsFile[1]

        # Running usersync to sync the newly created client
        gat.run_gen3_job(pytest.namespace, "usersync")
        # TODO : wait for usersync pod to finish and completed

        client_access_token_response = Gen3Auth(
            endpoint=pytest.root_url,
            client_credentials=(client_id, client_secret),
        )
        client_access_token = client_access_token_response._access_token

        # Creating data for request
        data = {"username": username, "policy_id": policy}

        request_id = requestor.create_request(data, client_access_token)

        # Getting the status of the request_id
        req_status = requestor.get_request_status(request_id)
        logger.info(f"Initial status of the request is {req_status}")

        # Updating the request from DRAFT to SIGNED state and check the status of the request
        requestor.request_signed(request_id)
        req_status_signed = requestor.get_request_status(request_id)
        logger.info(f"Status of the request is {req_status_signed}")

        logger.info("Starting the cleanup after the test ...")
        logger.info(f"Deleting the request id {request_id} from requestor db ...")
        if request_id:
            requestor.request_delete(request_id)

        # Delete the client from the fence db
        logger.info("Deleting client from the fence db ...")
        gat.delete_fence_client(pytest.namespace, "jenkinsClientTester")

        logger.info("Revoking arborist policy for the user ...")
        gat.revoke_arborist_policy(pytest.namespace, username, policy)
