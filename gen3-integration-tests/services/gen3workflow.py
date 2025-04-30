import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Tuple

import boto3
import botocore.exceptions
import pytest
import requests
from botocore.config import Config
from gen3.auth import Gen3Auth


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


def nextflow_parse_completed_line(line):
    """Parses a line from the log file that indicates a process has completed,
    to get its xx/yyyyyy identifier, finish time, return code, and status.

    :param str line: a line from the log file.
    :rtype: ``dict``"""

    parsed_dict = {
        "process_name": "-",
        "workDir": "-",
        "exit_code": "-",
        "status": "-",
    }
    log_pattern = (
        r"(?P<timestamp>\w{3}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) .*?"
        r"Task completed > TaskHandler\[.*?"
        r"name: (?P<name>.+); status: (?P<status>-?\w+); "
        r"exit: (?P<exit_code>-?\d+); "
        r".*?workDir: (?P<workDirProtocol>.+):\/\/(?P<workDir>.+)]"
    )
    match = re.match(log_pattern, line)

    if match:
        parsed_dict["process_name"] = match.group("name")
        parsed_dict["workDir"] = match.group("workDir")
        parsed_dict["workDirProtocol"] = match.group("workDirProtocol")
        parsed_dict["exit_code"] = match.group("exit_code")
        parsed_dict["status"] = match.group("status") or "-"
        if parsed_dict["exit_code"] != "0":
            parsed_dict["status"] = "FAILED"

    return parsed_dict


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
        filename: str = None,
    ):
        """Generic function for performing S3 actions like GET, PUT, DELETE."""
        access_token = self._get_access_token(user)
        client = self._get_s3_client(access_token, s3_storage_config)
        bucket, key = self._get_bucket_and_key(object_path)

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
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "NoSuchKey":
                assert (
                    expected_status == 404
                ), f"Received NoSuchKey error from s3_client when expected_status is {expected_status} instead of 404"
                return None
            elif error_code == "403":
                assert (
                    expected_status == 403
                ), f"Received an error from s3_client when expected_status is {expected_status} instead of 403. Error: {e}"
                return None
            raise  # Reraise for other errors

        assert (
            response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            == expected_status
        ), f"Expected {expected_status}, got {response['ResponseMetadata']['HTTPStatusCode']} when making an s3 request to perform {action} action on {bucket=} and {key=} "
        return response

    #############################
    ##### /storage endpoint #####
    #############################

    def get_storage_info(self, user: str = "main_account", expected_status=200) -> Dict:
        """Makes a GET request to the `/storage/info` endpoint."""
        storage_url = f"{self.BASE_URL}{self.SERVICE_URL}/storage/info"
        headers = (
            {
                "Content-Type": "application/json",
                "Authorization": f"bearer {self._get_access_token(user)}",
            }
            if user
            else {"Content-Type": "application/json"}
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
                "Content-Type": "application/json",
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
        response = self._perform_s3_action(
            "get", object_path, s3_storage_config, user, expected_status
        )
        return response["Body"].read().decode("utf-8") if response else None

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
        Takes in a request body and returns a task object with status 'CANCELING' or 'CANCELED'
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
        workflow_path: str,
        storage_config: WorkflowStorageConfig,
        user: str = "main_account",
    ):
        """
        Takes in a request body and returns a task object
        """
        access_token = self._get_access_token(user)
        os.environ["GEN3_TOKEN"] = access_token

        os.chdir(workflow_path)

        import nextflow

        # Run the Nextflow workflow
        execution = nextflow.run("./main.nf", configs=["./nextflow.config"])

        log_file_content = ""
        with open(".nextflow.log", "r") as log_file:
            log_file_content = log_file.read()
        assert (
            execution.status == "OK"
        ), f"Nextflow workflow execution failed with status: {execution.status} and log: {log_file_content}"

        # extract the lines from the log that contain the task completed message for parsing
        tes_task_info_list = [
            nextflow_parse_completed_line(line)
            for line in log_file_content.split("\n")
            if "Task completed > TaskHandler" in line
        ]

        task_s3_contents = {}
        for tes_task in tes_task_info_list:
            assert (
                tes_task["status"] == "COMPLETED"
            ), f"Task {tes_task['process_name']} failed with status: {tes_task['status']}"
            assert (
                tes_task["exit_code"] == "0"
            ), f"Task {tes_task['process_name']} failed with exit code: {tes_task['exit_code']}"
            assert (
                tes_task["workDirProtocol"] == "s3"
            ), f"Expected workDir to be an 's3' location, but got {tes_task['workDirProtocol']}"

            task_s3_contents[tes_task["process_name"]] = (
                self.list_bucket_objects_with_boto3(
                    folder_path=tes_task["workDir"],
                    s3_storage_config=storage_config,
                    user=user,
                )
            )
        map_task_name_to_output_file_name = {
            "extract_metadata (1)": {
                "filename": "dicom-metadata-img-1.dcm.csv",
                "command": "python3 /utils/extract_metadata.py img-1.dcm",
            },
            "extract_metadata (2)": {
                "filename": "dicom-metadata-img-2.dcm.csv",
                "command": "python3 /utils/extract_metadata.py img-2.dcm",
            },
            "dicom_to_png (1)": {
                "filename": "img-1.png",
                "command": "python3 /utils/dicom_to_png.py img-1.dcm",
            },
            "dicom_to_png (2)": {
                "filename": "img-2.png",
                "command": "python3 /utils/dicom_to_png.py img-2.dcm",
            },
        }
        for task_name, s3_contents in task_s3_contents.items():
            assert (
                len(s3_contents) > 0
            ), f"Expected to find files in the S3 bucket for task {task_name}, but got an empty list"

            print(f"Task {task_name} has the following files:")
            for file_info in s3_contents:
                print(file_info["Key"])

            assert map_task_name_to_output_file_name[task_name]["filename"] in [
                file["Key"].split("/")[-1] for file in s3_contents
            ], f"Expected to find {map_task_name_to_output_file_name[task_name]['filename']} in the S3 bucket for task {task_name}, but got {s3_contents}"

            command_file_name = [
                f"{file_info['Key']}"
                for file_info in s3_contents
                if file_info["Key"].endswith(".command.sh")
            ]
            assert (
                len(command_file_name) == 1
            ), f"Expected to find exactly one .command.sh file for task {task_name}, but got {len(command_file_name)}"
            command_file_name = command_file_name[0]
            # get contents of .command.sh file
            command_output_response = self.get_bucket_object_with_boto3(
                object_path=f"{storage_config.bucket_name}/{command_file_name}",
                s3_storage_config=storage_config,
                user=user,
            )

            assert (
                map_task_name_to_output_file_name[task_name]["command"]
                in command_output_response
            ), f"Expected to find {map_task_name_to_output_file_name[task_name]['command']} in the .command.sh file for task {task_name}, but got {command_output_response}"
