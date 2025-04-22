import os

import pytest
import utils.gen3_admin_tasks as gat
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from utils import logger


@pytest.mark.skipif(
    "fence" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.fence
@pytest.mark.requires_fence_client
class TestOIDCClient:
    def test_oidc_client_expiration(self):
        """
        Scenario: Test OIDC Client Expiration
        Steps:
            1. Create clients with various expiration times and with client_type = client_credentials
            2. Get client_id and client_secrets after each create request and store it
            3. Run `fence-delete-expired-clients` gen3job and check the logs for confirmation
        """
        clients = {
            "jenkins-client-no-expiration": pytest.clients[
                "jenkins-client-no-expiration"
            ],
            "jenkins-client-short-expiration": pytest.clients[
                "jenkins-client-short-expiration"
            ],
            "jenkins-client-medium-expiration": pytest.clients[
                "jenkins-client-medium-expiration"
            ],
            "jenkins-client-long-expiration": pytest.clients[
                "jenkins-client-long-expiration"
            ],
        }
        for client_name, client_details in clients.items():
            # checking if the access_token is created with client_id and client_secret
            gen3auth = Gen3Auth(
                endpoint=pytest.root_url,
                client_credentials=(
                    client_details["client_id"],
                    client_details["client_secret"],
                ),
            )
            client_access_token = gen3auth.get_access_token()
            assert client_access_token, "Client access token was not created"

        # running fence-delete-expired-clients job
        logs_contents = gat.fence_delete_expired_clients()

        # assertion from logs
        assert (
            "jenkins-client-no-expiration" not in logs_contents
        ), "jenkins-client-no-expiration found in logs"
        assert (
            "Some expired OIDC clients have been deleted!" in logs_contents
        ), 'Msg: "Some expired OIDC clients have been deleted!" not found in logs'
        assert (
            "jenkins-client-short-expiration" in logs_contents
        ), "jenkins-client-short-expiration not found in logs"
        assert (
            "Some OIDC clients are expiring soon!" in logs_contents
        ), 'Msg: "Some OIDC clients are expiring soon!" not found in logs'
        assert (
            "jenkins-client-medium-expiration" in logs_contents
        ), "jenkins-client-medium-expiration not found in logs"
        assert (
            "jenkins-client-long-expiration" not in logs_contents
        ), "jenkins-client-long-expiration found in logs"

        # Testing if the non-expired clients still work properly
        for client_name, client_details in clients.items():
            client_id, client_secret = (
                client_details["client_id"],
                client_details["client_secret"],
            )
            # you shouldnt be able to get access_token for client jenkins-client-short-expiration
            if client_name != "jenkins-client-short-expiration":
                gen3auth = Gen3Auth(
                    endpoint=pytest.root_url,
                    client_credentials=(client_id, client_secret),
                )
                client_token = gen3auth.get_access_token()
                logger.debug(
                    f"Access Token for client {client_name} after running fence job : {client_token}"
                )
                assert (
                    client_token
                ), f"Failed to get access token for client_id {client_id}"
            else:
                # expected result for client jenkins-client-short-expiration
                logger.info("Access Token is not found")

    def test_oidc_client_rotation(self):
        """
        Scenario: Test OIDC Client Rotation
        Steps:
            1. Create client `jenkins-client-tester` with client_type = client_credentials and store it as creds1
            2. Request client credentials rotation and new credentials as creds2
            3. Get access_token with help of client_credentials creds1 and cred2
            4. Send indexd post request to add indexd record and check if it successful request
        """
        client_name = "jenkins-client-tester"
        logger.info(f"Getting client_id and client_secret for client {client_name} ...")
        client_id = pytest.clients[client_name]["client_id"]
        client_secret = pytest.clients[client_name]["client_secret"]
        logger.info(client_id, client_secret)

        # Client is rotated as part of the setup, to enable test execution in parallel for this test suite.
        # Rotated client_id and client_secret are retrieved from pytest.rotated_clients.
        client_rotate_id = pytest.rotated_clients[client_name]["client_id"]
        client_rotate_secret = pytest.rotated_clients[client_name]["client_secret"]
        logger.info(client_rotate_id, client_rotate_secret)

        # Get access_token with client_id and client_secret before running client-fence-rotate command
        gen3auth_before = Gen3Auth(
            endpoint=pytest.root_url,
            client_credentials=(client_id, client_secret),
        )
        client_access_token = gen3auth_before.get_access_token()
        logger.debug(
            f"Client access token before client rotation : {client_access_token}"
        )
        assert client_access_token, "Client access token was not created"

        # Get access_token with client_id and client_secret after running client-fence-rotate
        gen3auth_after = Gen3Auth(
            endpoint=pytest.root_url,
            client_credentials=(client_rotate_id, client_rotate_secret),
        )
        client_rotate_access_token = gen3auth_after.get_access_token()
        logger.debug(
            f"Client access token after client rotation : {client_rotate_access_token}"
        )
        assert client_rotate_access_token, "Client access token was not created"

        data = {
            "file_name": "testfile",
            "size": 9,
            "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
            "urls": ["s3://mybucket/testfile"],
            "authz": ["/programs/jnkns/projects/jenkins"],
        }
        # sending indexd request with access_token before running client-fence-rotate
        index_before = Gen3Index(auth_provider=gen3auth_before)
        logger.info(
            "Creating index record with client creds before client rotation ... "
        )
        record1 = index_before.create_record(
            hashes=data["hashes"],
            urls=data["urls"],
            file_name=data["file_name"],
            size=data["size"],
            authz=data["authz"],
        )
        logger.debug(f'Indexd Record created with did : {record1["did"]}')
        assert record1["did"], "Indexd record not created successfully"

        # sending indexd request with access_token after running client-fence-rotate
        index_after = Gen3Index(auth_provider=gen3auth_after)
        logger.info(
            "Creating index record with client creds after client rotation ... "
        )
        record2 = index_after.create_record(
            hashes=data["hashes"],
            urls=data["urls"],
            file_name=data["file_name"],
            size=data["size"],
            authz=data["authz"],
        )
        logger.debug(f'Indexd Record created with did : {record2["did"]}')
        assert record2["did"], "Indexd record not created successfully"
