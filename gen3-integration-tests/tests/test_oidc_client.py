import pytest
import os

from utils import logger
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
import utils.gen3_admin_tasks as gat
from services.indexd import Indexd


@pytest.mark.fence
class TestOIDCClient:
    def test_oidc_client_expiration(self):
        """
        Scenario: Test OIDC Client Expiration
        Steps:
            1. Create clients with various expiration times and with client_type = client_credentials
            2. Get client_id and client_secrets after each create request and store it
            3. Run `fence-delete-expired-clients` gen3job and check the logs for confirmation
        """
        client_info = [
            ["jenkinsClientNoExpiration", ""],  # not in logs
            ["jenkinsClientShortExpiration", "0.00000000001"],  # in the logs
            ["jenkinsClientMediumExpiration", 4],  # in the logs
            ["jenkinsClientLongExpiration", 30],  # not in logs
        ]
        for client in client_info:
            client_name, expires_in = client
            logger.info(
                f"Creating client {client_name} expiring in {expires_in} days ..."
            )
            client_creds = gat.create_fence_client(
                pytest.namespace,
                client_name,
                "test-user",
                "client_credentials",
                None,
                expires_in,
            )
            credsFile = client_creds["client_creds.txt"].splitlines()
            if len(credsFile) < 2:
                raise Exception(
                    "Client credentials file does not contain expected data format (2 lines)"
                )
            client_id = credsFile[0]
            client_secret = credsFile[1]

            client.append(client_id)
            client.append(client_secret)

            # checking if the access_token is created with client_id and client_secret
            gen3auth = Gen3Auth(
                endpoint=pytest.root_url,
                client_credentials=(client_id, client_secret),
            )
            client_access_token = gen3auth.get_access_token()
            logger.debug(f"Client Access Token : {client_access_token}")
            assert client_access_token, "Client access token was not created"

        # running fence-delete-expired-clients job
        gat.run_gen3_job(pytest.namespace, "fence-delete-expired-clients")
        # checking the logs from the job pod
        job_logs = gat.check_job_pod(
            pytest.namespace, "fence-delete-expired-clients", "gen3job"
        )
        logs_contents = job_logs["logs.txt"]
        logger.debug(f"Logs: {logs_contents}")

        # assertion from logs
        assert (
            "jenkinsClientNoExpiration" not in logs_contents
        ), "jenkinsClientNoExpiration found in logs"
        assert (
            "Some expired OIDC clients have been deleted!" in logs_contents
        ), 'Msg: "Some expired OIDC clients have been deleted!" not found in logs'
        assert (
            "jenkinsClientShortExpiration" in logs_contents
        ), "jenkinsClientShortExpiration not found in logs"
        assert (
            "Some OIDC clients are expiring soon!" in logs_contents
        ), 'Msg: "Some OIDC clients are expiring soon!" not found in logs'
        assert (
            "jenkinsClientMediumExpiration" in logs_contents
        ), "jenkinsClientMediumExpiration not found in logs"
        assert (
            "jenkinsClientLongExpiration" not in logs_contents
        ), "jenkinsClientLongExpiration found in logs"

        # Testing if the non-expired clients still work properly
        for client in client_info:
            client_name, _, client_id, client_secret = client
            # you shouldnt be able to get access_token for client jenkinsClientShortExpiration
            if client_name != "jenkinsClientShortExpiration":
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
                # expected result for client jenkinsClientShortExpiration
                logger.info("Access Token is not found")

        # Deleting clients after the test is done
        for client in client_info:
            client_name, _, client_id, client_secret = client
            logger.info(f"Deleting {client_name} from fence DB ...")
            gat.delete_fence_client(pytest.namespace, client_name)

    def test_oidc_client_rotation(self):
        """
        Scenario: Test OIDC Client Rotation
        Steps:
            1. Create client `jenkinsClientTester` with client_type = client_credentials and store it as creds1
            2. Request client credentials rotation and new credentials as creds2
            3. Run usersync gen3job
            4. Get access_token with help of client_credentials creds1 and cred2
            5. Send indexd post request to add indexd record and check if it successful request
        """
        client_name = "jenkinsClientTester"
        logger.info(f"Creating client {client_name} ...")
        client_creds = gat.create_fence_client(
            pytest.namespace,
            client_name,
            "test-user",
            "client_credentials",
        )
        # Get credentials before run client-rotate command in fence pod for client
        credsFile = client_creds["client_creds.txt"].splitlines()
        if len(credsFile) < 2:
            raise Exception(
                "Client credentials file does not contain expected data format (2 lines)"
            )
        client_id = credsFile[0]
        client_secret = credsFile[1]

        # Run client-rotate command in fence pod for client
        logger.info(f"Rotating creds for client {client_name} ...")
        client_rotate_creds = gat.fence_client_rotate(pytest.namespace, client_name)
        rotate_client = client_rotate_creds["client_rotate_creds.txt"].splitlines()
        if len(rotate_client) < 2:
            raise Exception(
                "Client Rotation creds file does not contain expected data format (2 lines)"
            )
        client_rotate_id = rotate_client[0]
        client_rotate_secret = rotate_client[1]

        gat.run_gen3_job(pytest.namespace, "usersync")
        gat.check_job_pod(pytest.namespace, "usersync", "gen3job")

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
        record1 = index_before.create_record(
            hashes=data["hashes"],
            urls=data["urls"],
            file_name=data["file_name"],
            size=data["size"],
            authz=data["authz"],
        )
        logger.debug(f"Indexd Record created with did : {record1["did"]}")
        assert record1["did"], "Indexd record not created successfully"

        # sending indexd request with access_token after running client-fence-rotate
        index_after = Gen3Index(auth_provider=gen3auth_after)
        record2 = index_after.create_record(
            hashes=data["hashes"],
            urls=data["urls"],
            file_name=data["file_name"],
            size=data["size"],
            authz=data["authz"],
        )
        logger.debug(f"Indexd Record created with did : {record2["did"]}")
        assert record2["did"], "Indexd record not created successfully"

        # deleting client after the test
        logger.info(f"Deleting client jenkinsClientTester from fence DB ...")
        gat.delete_fence_client(pytest.namespace, "jenkinsClientTester")
