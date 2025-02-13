from typing import Dict, Tuple

import boto3
import botocore.exceptions
import pytest
import requests
from gen3.auth import Gen3Auth
from utils import logger


class Gen3Workflow:
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}"
        self.SERVICE_URL = "/workflows"
        self.S3_ENDPOINT_URL = f"{self.BASE_URL}{self.SERVICE_URL}/s3"

    def _get_access_token(self, user: str = "main_account") -> str:
        """Helper function to retrieve an access token."""
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        return auth.get_access_token()

    def _get_s3_client(self, access_token: str):
        """Creates and returns an S3 client."""
        return boto3.client(
            service_name="s3",
            aws_access_key_id=access_token,
            aws_secret_access_key="N/A",  # pragma: allowlist secret
            endpoint_url=self.S3_ENDPOINT_URL,
        )

    def _get_bucket_and_key(self, object_path: str) -> Tuple[str, str]:
        """Parses object_path into bucket and key."""
        # cleaner than using the string.split() method
        bucket, _, key = object_path.partition("/")
        return bucket, key

    def get_storage_info(self, user: str = "main_account", expected_status=200) -> Dict:
        """Makes a GET request to the `/storage/info` endpoint."""
        access_token = self._get_access_token(user) if user else None
        storage_url = f"{self.BASE_URL}{self.SERVICE_URL}/storage/info"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"bearer {access_token}",
        }

        response = requests.get(url=storage_url, headers=headers)
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status}, got {response.status_code}"

        return response.json()

    def get_bucket_object_with_unsigned_request(
        self, object_path: str, user: str = "main_account", expected_status=401
    ):
        """Attempts to get an object without signing the request, expecting a failure."""
        access_token = self._get_access_token(user)
        s3_url = f"{self.S3_ENDPOINT_URL}/{object_path}"
        headers = {"Authorization": f"bearer {access_token}"}

        response = requests.get(url=s3_url, headers=headers)
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status}, got {response.status_code}"

    def perform_s3_action(
        self,
        action: str,
        object_path: str,
        user: str = "main_account",
        expected_status=200,
        content: str = None,
    ):
        """Generic function for performing S3 actions like GET, PUT, DELETE."""
        access_token = self._get_access_token(user)
        client = self._get_s3_client(access_token)
        bucket, key = self._get_bucket_and_key(object_path)

        if action == "list":
            response = client.list_objects_v2(Bucket=bucket, Prefix=key)
        elif action == "get":
            response = client.get_object(Bucket=bucket, Key=key)
        elif action == "put":
            response = client.put_object(Bucket=bucket, Key=key, Body=content or "")
        elif action == "delete":
            response = client.delete_object(Bucket=bucket, Key=key)
        else:
            raise ValueError(f"Unsupported S3 action: {action}")

        assert (
            response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            == expected_status
        ), f"Expected {expected_status}, got {response['ResponseMetadata']['HTTPStatusCode']}"
        return response

    def get_bucket_object_with_boto3(
        self, object_path: str, user: str = "main_account", expected_status=200
    ):
        """Retrieves an S3 object."""
        try:
            response = self.perform_s3_action("get", object_path, user, expected_status)
            return response["Body"].read().decode("utf-8")
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchKey":
                assert (
                    expected_status == 404
                ), f"Received NoSuchKey error from s3_client when expected_status is {expected_status} instead of 404"
                return None
            raise  # Reraise for other errors

    def list_bucket_objects_with_boto3(
        self, folder_path: str, user: str = "main_account", expected_status=200
    ):
        """Retrieves a list of all S3 objects present in the given folder path."""
        response = self.perform_s3_action("list", folder_path, user, expected_status)
        return response.get("Contents")

    def put_bucket_object_with_boto3(
        self,
        content: str,
        object_path: str,
        user: str = "main_account",
        expected_status=200,
    ):
        """Uploads an object to S3."""
        self.perform_s3_action("put", object_path, user, expected_status, content)

    def delete_bucket_object_with_boto3(
        self, object_path: str, user: str = "main_account", expected_status=200
    ):
        """Deletes an object from S3."""
        self.perform_s3_action("delete", object_path, user, expected_status)
