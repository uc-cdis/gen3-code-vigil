import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import boto3
import botocore.exceptions
import nextflow
import pytest
import requests
from botocore.config import Config
from gen3.auth import Gen3Auth
from utils import logger


@dataclass(frozen=True)
class WorkflowStorageConfig:
    """
    Represents the storage configuration details required for working with the S3 bucket in Gen3Workflow.

    Attributes:
        bucket (str): The name of the S3 bucket.
        workdir (str): The full S3 URI for the working directory within the bucket.
        region (str): The AWS region where the S3 bucket is located.
    """

    bucket_name: str
    working_directory: str
    bucket_region: str

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowStorageConfig":
        """
        Creates an instance of StorageConfig from a dictionary.

        Args:
            data (dict): A dictionary containing storage configuration details.

        Returns:
            StorageConfig: An instance of the StorageConfig class.
        """
        required_keys = ["bucket", "workdir", "region"]

        # Ensure all required keys are present
        for key in required_keys:
            if key not in data:
                raise ValueError(f"Missing value for key: '{key}' in StorageConfig")

        return cls(
            bucket_name=data["bucket"],
            working_directory=data["workdir"],
            bucket_region=data["region"],
        )


class Gen3Workflow:
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}"
        self.SERVICE_URL = "/workflows"
        self.TES_URL = f"{self.BASE_URL}/ga4gh/tes/v1"
        self.S3_ENDPOINT_URL = f"{self.BASE_URL}{self.SERVICE_URL}/s3"

    ############################
    ##### Helper Functions #####
    ############################

    def _get_access_token(self, user: str = "main_account") -> str:
        """Helper function to retrieve an access token."""

        if not user:
            return None

        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        return auth.get_access_token()

    def _get_s3_client(
        self, access_token: str, s3_storage_config: WorkflowStorageConfig
    ):
        """Creates and returns an S3 client."""
        return boto3.client(
            service_name="s3",
            aws_access_key_id=access_token,
            aws_secret_access_key="N/A",
            endpoint_url=self.S3_ENDPOINT_URL,
            config=Config(region_name=s3_storage_config.bucket_region),
        )

    def _get_bucket_and_key(self, object_path: str) -> Tuple[str, str]:
        """Parses object_path into bucket and key."""
        # cleaner than using the string.split() method
        bucket, _, key = object_path.partition("/")
        return bucket, key

    def _perform_s3_action(
        self,
        action: str,
        object_path: str,
        s3_storage_config: WorkflowStorageConfig,
        user: str = "main_account",
        expected_status=200,
        content: str = None,
    ):
        """Generic function for performing S3 actions like GET, PUT, DELETE through the gen3-workflow /s3 endpoint"""
        access_token = self._get_access_token(user)
        client = self._get_s3_client(access_token, s3_storage_config)
        bucket, key = self._get_bucket_and_key(object_path)
        logger.debug(
            f"Performing {action=} on {bucket=} and {key=}. More info: {user=} and {content=}"
        )
        response = None
        try:
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

            response_status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            logger.debug(f"S3 {action.upper()} response:  {response}")

        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchKey":
                response_status = 404
            elif error_code == "403":
                response_status = 403
            else:
                logger.error(
                    f"Received an error from s3_client when expected_status is {expected_status}. Error: {e.response}"
                )
                raise  # Reraise for other errors
        assert (
            response_status == expected_status
        ), f"Expected {expected_status}, got {response_status} when making an s3 request to perform {action} action on {bucket=} and {key=}. Response: {response}"
        return response

    #############################
    ##### /storage endpoint #####
    #############################

    def get_storage_info(self, user: str = "main_account", expected_status=200) -> Dict:
        """Makes a GET request to the `/storage/info` endpoint."""
        storage_url = f"{self.BASE_URL}{self.SERVICE_URL}/storage/info"
        headers = (
            {
                "Authorization": f"bearer {self._get_access_token(user)}",
            }
            if user
            else {}
        )

        response = requests.get(url=storage_url, headers=headers)
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status}, got {response.status_code} when making a GET request to {storage_url}"
        storage_info = response.json()
        assert isinstance(storage_info, dict), "Expected a valid JSON response"
        return storage_info

    def delete_user_bucket(
        self, user: str = "main_account", ignore_missing=True, expected_status=204
    ) -> None:
        """
        Makes a DELETE request to the `/storage/user-bucket` endpoint.
        This endpoint is used to delete the user's bucket in the Gen3 Workflow service.
        Args:
            user (str): The user whose bucket is to be deleted. Defaults to "main_account".
            ignore_missing (bool): If True, suppress error when the bucket does not exist (i.e., 404).
            expected_status (int): Expected successful status code (default: 204 No Content).
        Raises:
            AssertionError: If the response status code does not match the expected status.

        """
        delete_bucket_url = f"{self.BASE_URL}{self.SERVICE_URL}/storage/user-bucket"
        headers = (
            {
                "Authorization": f"bearer {self._get_access_token(user)}",
            }
            if user
            else {}
        )
        response = requests.delete(url=delete_bucket_url, headers=headers)

        # If ignore_missing is True, we allow 404 as a valid response status
        allowed_statuses = (
            [expected_status, 404] if ignore_missing else [expected_status]
        )

        assert (
            response.status_code in allowed_statuses
        ), f"Expected one of {allowed_statuses}, got {response.status_code} when making a DELETE request to {delete_bucket_url}"

    ###############################################
    ###### /s3 endpoint and boto3 functions #######
    ###############################################

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
        ), f"Expected {expected_status}, got {response.status_code} when attempting to make an unsigned GET request to {s3_url}"

    def get_bucket_object_with_boto3(
        self,
        object_path: str,
        s3_storage_config: WorkflowStorageConfig,
        user: str = "main_account",
        expected_status=200,
    ):
        """Retrieves an S3 object."""
        return self._perform_s3_action(
            "get", object_path, s3_storage_config, user, expected_status
        )

    def list_bucket_objects_with_boto3(
        self,
        folder_path: str,
        s3_storage_config: WorkflowStorageConfig,
        user: str = "main_account",
        expected_status=200,
    ):
        """Retrieves a list of all S3 objects present in the given folder path."""
        response = self._perform_s3_action(
            "list", folder_path, s3_storage_config, user, expected_status
        )
        return response.get("Contents")

    def put_bucket_object_with_boto3(
        self,
        content: str,
        object_path: str,
        s3_storage_config: WorkflowStorageConfig,
        user: str = "main_account",
        expected_status=200,
    ):
        """Uploads an object to S3."""
        self._perform_s3_action(
            "put",
            object_path,
            s3_storage_config,
            user,
            expected_status,
            content=content,
        )

    def delete_bucket_object_with_boto3(
        self,
        object_path: str,
        s3_storage_config: WorkflowStorageConfig,
        user: str = "main_account",
        expected_status=200,
    ):
        """Deletes an object from S3."""
        self._perform_s3_action(
            "delete", object_path, s3_storage_config, user, expected_status
        )

    ######################################################
    ######### /ga4gh/tes/v1/ endpoint functions ##########
    ######################################################

    def create_tes_task(
        self, request_body: dict, user: str = "main_account", expected_status=200
    ) -> str:
        """
        Takes in a request body and returns a string containing the task_id
        """
        access_token = self._get_access_token(user)
        tes_task_url = f"{self.TES_URL}/tasks"
        headers = {"Authorization": f"bearer {access_token}"} if user else {}
        response = requests.post(
            url=tes_task_url,
            headers=headers,
            json=request_body,
        )
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status}, got {response.status_code} when attempting to make a POST request to {tes_task_url}"
        return response.json()

    def list_tes_tasks(self, user: str = "main_account", expected_status=200):
        """
        Takes in a request body and returns a list of task objects
        """
        access_token = self._get_access_token(user)
        tes_task_url = f"{self.TES_URL}/tasks"
        response = requests.get(
            url=tes_task_url,
            headers={"Authorization": f"bearer {access_token}"} if user else {},
        )
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status}, got {response.status_code} when attempting to make a GET request to {tes_task_url}"
        return response.json()

    def get_tes_task(
        self, task_id: str, user: str = "main_account", expected_status=200
    ):
        """
        Takes in a request body and returns a task object
        """
        access_token = self._get_access_token(user)
        tes_task_url = f"{self.TES_URL}/tasks/{task_id}"

        response = requests.get(
            url=tes_task_url,
            headers={"Authorization": f"bearer {access_token}"} if user else {},
        )
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status}, got {response.status_code} when attempting to make a GET request to {tes_task_url}"
        return response.json()

    def cancel_tes_task(
        self, task_id: str, user: str = "main_account", expected_status=200
    ):
        """
        Takes in a request body and returns a task object which should have status 'CANCELING' or 'CANCELED'
        """
        access_token = self._get_access_token(user)
        tes_task_url = f"{self.TES_URL}/tasks/{task_id}:cancel"

        response = requests.post(
            url=tes_task_url,
            headers={"Authorization": f"bearer {access_token}"} if user else {},
        )
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status}, got {response.status_code} when attempting to make an POST request to {tes_task_url}"
        return response.json()

    def run_nextflow_task(
        self,
        workflow_dir: str,
        workflow_script: str,
        nextflow_config_file: str,
        s3_working_directory: str,
        user: str = "main_account",
    ):
        """
        Runs a Nextflow workflow using the given workflow script and config file.

        Parameters:
            workflow_dir (str): Path to the directory containing the workflow.
            workflow_script (str): Filename of the main Nextflow script (e.g., main.nf).
            nextflow_config_file (str): Path to the nextflow.config file.
            s3_working_directory (str): S3 URI for the working directory (e.g., s3://bucket/workdir).
            user (str): User context to run the workflow under.

        Returns:
            str: Contents of the Nextflow log file (.nextflow.log).
        """
        access_token = self._get_access_token(user)
        os.environ["GEN3_TOKEN"] = access_token
        os.environ["HOSTNAME"] = pytest.hostname
        os.environ["WorkDir"] = s3_working_directory

        original_cwd = Path.cwd()
        workflow_dir_path = Path(workflow_dir).resolve()

        try:
            os.chdir(workflow_dir_path)
            # Run the Nextflow workflow
            execution = nextflow.run(workflow_script, configs=[nextflow_config_file])

            log_file_content = ""
            with open(".nextflow.log", "r") as log_file:
                log_file_content = log_file.read()
            assert (
                execution.status == "OK"
            ), f"Nextflow workflow execution failed with status: {execution.status} and log: {log_file_content}"

            return log_file_content
        finally:
            # Change back to the original working directory
            os.chdir(original_cwd)
