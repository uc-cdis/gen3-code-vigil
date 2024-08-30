import pytest
import requests
import os
import json

from gen3.auth import Gen3Auth
from services.requestor import Requestor
from services.fence import Fence
import utils.gen3_admin_tasks as gat

from utils import logger


@pytest.mark.client_credentials
@pytest.mark.fence
@pytest.mark.requestor
@pytest.mark.requires_fence_client
@pytest.mark.requires_usersync
class TestClientCredentials:
    def test_client_credentials(self):
        """
        Scenario: Test Client Credentials
        Steps:
            1. Create a client in Fence Db with grant_type=client_credential and run usersync (done in the test setup)
            2. Create a client_access_token from the client_id and client_secret
            3. Create a new Requestor request with client_access_token
            4. Update the request to SIGNED status
        """
        fence = Fence()
        client_access_token = None
        request_id = None
        username = pytest.users["user0_account"]
        policy = "requestor_client_credentials_test"
        requestor = Requestor()

        # creating a new client for the test
        client_id = pytest.clients["jenkins-client-tester"]["client_id"]
        client_secret = pytest.clients["jenkins-client-tester"]["client_secret"]

        gen3auth = Gen3Auth(
            endpoint=pytest.root_url,
            client_credentials=(client_id, client_secret),
        )
        client_access_token = gen3auth.get_access_token()

        # Creating data for request
        data = {"username": username, "policy_id": policy}

        request_id = requestor.create_request_with_client_token(
            data, client_access_token
        )

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

        logger.info("Revoking arborist policy for the user ...")
        gat.revoke_arborist_policy(pytest.namespace, username, policy)
