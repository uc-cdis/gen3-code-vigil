import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple
from unittest.mock import patch

import boto3
import botocore.exceptions
import nextflow
import pytest
import requests
from botocore.config import Config
from gen3.auth import (
    Gen3Auth,
    endpoint_from_token,
    remove_trailing_whitespace_and_slashes_in_url,
)
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


def _print_tes_apps_logs(describe_task_pods=False, with_arborist=False):
    apps = ["gen3-workflow", "funnel"]
    if with_arborist:
        apps.append("arborist")
    for app in apps:
        logger.info(f"********** {app} logs begin **********")
        cmd = [
            "kubectl",
            "-n",
            pytest.namespace,
            "logs",
            "-l",
            f"app={app}",
            "--all-containers",
            "--tail",
            "10" if app == "arborist" else "150",
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            logger.info(result.stdout.decode("utf-8"))
        else:
            logger.info(
                f"Unable to get {app} logs: code {result.returncode}. Stderr: {result.stderr.decode('utf-8')}"
            )
        logger.info(f"********** {app} logs end **********")

    if describe_task_pods:
        # list the jobs in the JobsNamespace
        cmd = [
            "kubectl",
            "-n",
            f"workflow-pods-{pytest.namespace}",
            "get",
            "jobs",
        ]
        logger.info(f"********** {" ".join(cmd)} **********")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            logger.info(result.stdout.decode("utf-8"))
        else:
            logger.info(
                f"{" ".join(cmd)} failed: code {result.returncode}. Stderr: {result.stderr.decode('utf-8')}"
            )

        # list the pods in the JobsNamespace
        cmd = [
            "kubectl",
            "-n",
            f"workflow-pods-{pytest.namespace}",
            "get",
            "pods",
        ]
        logger.info(f"********** {" ".join(cmd)} **********")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            logger.info(result.stdout.decode("utf-8"))
        else:
            logger.info(
                f"{" ".join(cmd)} failed: code {result.returncode}. Stderr: {result.stderr.decode('utf-8')}"
            )

        # describe all the pods in the JobsNamespace
        cmd = [
            "kubectl",
            "-n",
            f"workflow-pods-{pytest.namespace}",
            "describe",
            "pod",
        ]
        logger.info(f"********** {" ".join(cmd)} **********")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            logger.info(result.stdout.decode("utf-8"))
        else:
            logger.info(
                f"Unable to get {app} logs: code {result.returncode}. Stderr: {result.stderr.decode('utf-8')}"
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

    @patch("gen3.auth.endpoint_from_token")
    def _get_access_token(
        self, user: str = "main_account", endpoint_from_token_mock=None
    ) -> str:
        """Helper function to retrieve an access token."""

        if not user:
            return None

        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)

        # When running the tests in a Kind cluster:
        # - Fence's `BASE_URL` is set to `http://fence-service.<namespace>.svc.cluster.local`, so
        #   API keys and access tokens have that as their issuer. This allows other pods in the
        #   cluster to reach Fence to validate tokens.
        # - However, the tests cannot reach this URL from outside the cluster. The cluster is
        #   exposed at `http://localhost:8000` and that's where the tests can reach Fence to obtain
        #   access tokens.
        # - The SDK's `endpoint_from_token` method extracts the endpoint from the API key. We mock
        #   this method to return `http://localhost:8000` instead of `http://fence-service.
        #   <namespace>.svc.cluster.local` so `Gen3Auth` knows to reach Fence there.
        # - Note: Setting Fence's `BASE_URL` to `http://localhost:8000` would fix this on the tests
        #   side, but other pods in the cluster would not be able to reach Fence to validate tokens
        #   (because within a container, localhost refers to the container itself).
        if "localhost" in self.BASE_URL:
            endpoint_from_token_mock.return_value = (
                remove_trailing_whitespace_and_slashes_in_url(self.BASE_URL)
            )
        else:  # otherwise, no mocking
            endpoint_from_token_mock.side_effect = lambda arg: endpoint_from_token(arg)

        try:
            return auth.get_access_token()
        except Exception:
            logger.info("Failed to get access token with Gen3Auth")
            raise

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
        content: str = "",
        filename: str = "",
        dest_object_path: str = "",
        range: str = "",
        config=None,
    ):
        """Generic function for performing S3 actions like GET, PUT, DELETE through the gen3-workflow /s3 endpoint"""
        access_token = self._get_access_token(user)
        client = self._get_s3_client(access_token, s3_storage_config)
        bucket, key = self._get_bucket_and_key(object_path)
        logger.info(
            f"Performing {action=} on {bucket=} and {key=}. More info: {user=} and content={content[:100]}{'[...]' if len(content) > 100 else ''}"
        )
        response = None
        try:
            if action == "list":
                response = client.list_objects_v2(Bucket=bucket, Prefix=key)
            elif action == "get":
                response = client.get_object(
                    Bucket=bucket, Key=key, Range=f"bytes=0-{range-1}" if range else ""
                )
            elif action == "put":
                response = client.put_object(Bucket=bucket, Key=key, Body=content or "")
            elif action == "upload_file":
                response = client.upload_file(
                    Filename=filename, Bucket=bucket, Key=key, Config=config
                )
            elif action == "copy":
                dest_bucket, dest_key = self._get_bucket_and_key(dest_object_path)
                response = client.copy(
                    CopySource={"Bucket": bucket, "Key": key},
                    Bucket=dest_bucket,
                    Key=dest_key,
                    Config=config,
                )
            elif action == "delete":
                response = client.delete_object(Bucket=bucket, Key=key)
            else:
                raise ValueError(f"Unsupported S3 action: {action}")
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            _print_tes_apps_logs(with_arborist=error_code == "403")
            if error_code == "NoSuchKey":
                response_status = 404
            elif error_code == "403":
                response_status = 403
            else:
                logger.error(
                    f"Received an error from s3_client, expected status was {expected_status}. Error: {e.response}"
                )
                raise  # Reraise for other errors
        except Exception as e:
            _print_tes_apps_logs()
            logger.error(f"Received an error from s3_client. Error: {e}")
            raise
        else:
            response_status = (
                response.get("ResponseMetadata", {}).get("HTTPStatusCode")
                if response
                else None
            )
        logger.debug(f"S3 {action.upper()} response:  {response}")

        assert (
            response_status == expected_status
        ), f"Expected {expected_status}, got {response_status} when making an s3 request to perform {action} action on {bucket=} and {key=}. Response: {response}"
        return response

    def poll_until_task_reaches_expected_state(
        self, task_id, user, expected_final_state, max_retries=15, poll_interval=30
    ):
        """
        Polls the TES task status until it reaches a final state or exceeds max retries.

        :param task_id: ID of the TES task to poll.
        :param user: User credentials for authentication.
        :param expected_final_state: Final state, which this task is expected to return (e.g., {"COMPLETE", "FAILED"}).
        :param max_retries: Maximum number of polling attempts before giving up.
        :param poll_interval: Time in seconds between polling attempts.
        :return: Final task information if completed successfully.
        :raises Exception: If the task fails or does not complete in time.
        """
        transient_states = {"QUEUED", "INITIALIZING", "RUNNING"}
        final_states = {
            "COMPLETE",
            "FAILED",
            "EXECUTOR_ERROR",
            "CANCELED",
            "SYSTEM_ERROR",
        }
        logger.info(f"Monitoring task '{task_id}'")
        try:
            for attempt in range(1, max_retries + 1):
                task_info = self.get_tes_task(
                    task_id=task_id,
                    user=user,
                    expected_status=200,
                )
                state = task_info.get("state")

                if state == expected_final_state:
                    logger.info(
                        f"TES task reached final state '{state}', Response: {json.dumps(task_info, indent=2)}"
                    )
                    return task_info

                assert (
                    state not in final_states
                ), f"TES task reached a final state that is not the expected '{expected_final_state}'. Final state: {state}, Response: {json.dumps(task_info, indent=2)}"
                assert (
                    state in transient_states
                ), f"Unexpected TES task state '{state}' encountered. Response: {json.dumps(task_info, indent=2)}"

                logger.info(
                    f"Check {attempt}/{max_retries}: Task state is '{state}', retrying in {poll_interval}s..."
                )
                if attempt <= max_retries:
                    time.sleep(poll_interval)

            raise Exception(
                f"TES task did not reach a final state in time. Last known state: '{state}', Response: {json.dumps(task_info, indent=2)}"
            )
        except Exception:
            _print_tes_apps_logs(describe_task_pods=True)
            raise

    #############################
    ##### /storage endpoint #####
    #############################

    def setup_storage(self, user: str = "main_account", expected_status=200) -> Dict:
        """Makes a GET request to the `/storage/setup` endpoint."""
        storage_url = f"{self.BASE_URL}{self.SERVICE_URL}/storage/setup"
        headers = (
            {
                "Authorization": f"bearer {self._get_access_token(user)}",
            }
            if user
            else {}
        )

        response = requests.get(url=storage_url, headers=headers)
        if response.status_code != expected_status:
            _print_tes_apps_logs(with_arborist=response.status_code == 403)
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status}, got {response.status_code} when making a GET request to {storage_url}: {response.text}"
        storage_info = response.json()
        assert isinstance(storage_info, dict), "Expected a valid JSON response"
        return storage_info

    def cleanup_user_bucket(
        self,
        user: str = "main_account",
        ignore_missing=True,
        delete_bucket=False,
        expected_status=204,
    ) -> None:
        """
        Makes a DELETE request to the `/storage/user-bucket/objects` endpoint.
        This endpoint is used to delete the objects in a user's bucket in the Gen3 Workflow service.
        Args:
            user (str): The user whose bucket is to be deleted. Defaults to "main_account".
            ignore_missing (bool): If True, suppress error when the bucket does not exist (i.e., 404).
            delete_bucket(bool): If True, the s3 bucket is also deleted along with the object by making a request to DELETE /storage/user-bucket
            expected_status (int): Expected successful status code (default: 204 No Content).
        Raises:
            AssertionError: If the response status code does not match the expected status.

        """

        cleanup_url = (
            f"{self.BASE_URL}{self.SERVICE_URL}/storage/user-bucket"
            if delete_bucket
            else f"{self.BASE_URL}{self.SERVICE_URL}/storage/user-bucket/objects"
        )
        headers = (
            {
                "Authorization": f"bearer {self._get_access_token(user)}",
            }
            if user
            else {}
        )
        response = requests.delete(url=cleanup_url, headers=headers)

        # If ignore_missing is True, we allow 404 as a valid response status
        allowed_statuses = (
            [expected_status, 404] if ignore_missing else [expected_status]
        )
        if response.status_code not in allowed_statuses:
            _print_tes_apps_logs(with_arborist=response.status_code == 403)
        assert (
            response.status_code in allowed_statuses
        ), f"Expected one of {allowed_statuses}, got {response.status_code} when making a DELETE request to {cleanup_url}: {response.text}"

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
        ), f"Expected {expected_status}, got {response.status_code} when attempting to make an unsigned GET request to {s3_url}: {response.text}"

    def get_bucket_object_with_boto3(
        self,
        object_path: str,
        s3_storage_config: WorkflowStorageConfig,
        user: str = "main_account",
        expected_status=200,
        range: str = "",
    ):
        """Retrieves an S3 object."""
        return self._perform_s3_action(
            "get", object_path, s3_storage_config, user, expected_status, range=range
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

        # Avoid adding `x-amz-checksum-crc32` data to the file contents
        # See https://github.com/boto/boto3/issues/4435
        os.environ["AWS_REQUEST_CHECKSUM_CALCULATION"] = "when_required"
        os.environ["AWS_RESPONSE_CHECKSUM_VALIDATION"] = "when_required"

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
        if response.status_code != expected_status:
            _print_tes_apps_logs(with_arborist=response.status_code == 403)
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status}, got {response.status_code} when attempting to make a POST request to {tes_task_url}: {response.text}"
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
        if response.status_code != expected_status:
            _print_tes_apps_logs(with_arborist=response.status_code == 403)
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status}, got {response.status_code} when attempting to make a GET request to {tes_task_url}: {response.text}"
        return response.json()

    def get_tes_task(
        self, task_id: str, user: str = "main_account", expected_status=200
    ):
        """
        Takes in a request body and returns a task object
        """
        access_token = self._get_access_token(user)
        tes_task_url = f"{self.TES_URL}/tasks/{task_id}?view=FULL"

        response = requests.get(
            url=tes_task_url,
            headers={"Authorization": f"bearer {access_token}"} if user else {},
        )
        if response.status_code != expected_status:
            _print_tes_apps_logs(with_arborist=response.status_code == 403)
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status}, got {response.status_code} when attempting to make a GET request to {tes_task_url}: {response.text}"
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
        if response.status_code != expected_status:
            _print_tes_apps_logs(with_arborist=response.status_code == 403)
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status}, got {response.status_code} when attempting to make an POST request to {tes_task_url}: {response.text}"
        return response.json()

    def run_nextflow_workflow(
        self,
        workflow_dir: str,
        workflow_script: str,
        nextflow_config_file: str,
        s3_working_directory: str,
        user: str = "main_account",
        params: dict = {},
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
        os.environ["HOSTNAME_PROTOCOL"] = os.getenv("HOSTNAME_PROTOCOL")
        os.environ["WORK_DIR"] = s3_working_directory

        original_cwd = Path.cwd()
        workflow_dir_path = Path(workflow_dir).resolve()

        try:
            os.chdir(workflow_dir_path)
            # Run the Nextflow workflow
            # TODO: Replace nextflow.run with nextflow.run_and_poll to add a timeout of 10 minutes
            execution = nextflow.run(
                workflow_script, configs=[nextflow_config_file], params=params
            )

            log_file_content = ""
            with open(".nextflow.log", "r") as log_file:
                log_file_content = log_file.read()
            if execution.status != "OK":
                _print_tes_apps_logs(describe_task_pods=True)
            assert (
                execution.status == "OK"
            ), f"Nextflow workflow execution failed with status: {execution.status} and log:\n{log_file_content}"

            return log_file_content
        finally:
            # Change back to the original working directory
            os.chdir(original_cwd)
