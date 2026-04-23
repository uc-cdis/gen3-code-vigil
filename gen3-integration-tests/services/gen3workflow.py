import os
import subprocess
import time
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


import base64
import json

# from urllib.parse import urlparse


def decode_token(token_str):
    """
    jq -r '.api_key' < ~/.gen3/qa-covid19.planx-pla.net.json | awk -F . '{ print $2 }' | base64 --decode | jq -r .
    """
    tokenParts = token_str.split(".")
    if len(tokenParts) < 3:
        raise Exception("Invalid JWT. Could not split into parts.")
    padding = "===="
    infoStr = tokenParts[1] + padding[0 : len(tokenParts[1]) % 4]
    jsonStr = base64.urlsafe_b64decode(infoStr)
    return json.loads(jsonStr)


# def remove_trailing_whitespace_and_slashes_in_url(url):
#     """
#     Given a url, remove any whitespace and then slashes at the end and return url
#     """
#     logger.info(f"url = {url}")
#     if url:
#         return url.rstrip().rstrip("/")
#     return url


# def endpoint_from_token(token_str):
#     """
#     Extract the endpoint from a JWT issue ("iss" property)
#     """
#     info = decode_token(token_str)
#     logger.info(f"info = {info}")
#     urlparts = urlparse(info["iss"])
#     logger.info(f"urlparts = {urlparts}")
#     endpoint = urlparts.scheme + "://" + urlparts.hostname
#     logger.info(f"urlparts.port = {urlparts.port}")
#     if urlparts.port:
#         endpoint += ":" + str(urlparts.port)
#     logger.info(f"endpoint = {endpoint}")
#     return remove_trailing_whitespace_and_slashes_in_url(endpoint)


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
        # logger.info(f"_get_access_token self.BASE_URL = {self.BASE_URL}")
        # logger.info(f"pytest.api_keys[user] = {pytest.api_keys[user]}")
        # endpoint = endpoint_from_token(pytest.api_keys[user]["api_key"])
        # logger.info(f"final endpoint = {endpoint}")

        if not user:
            return None

        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        logger.info(f"auth.endpoint = {auth.endpoint}")
        try:
            t = auth.get_access_token()
            logger.info(f"_get_access_token token info = {decode_token(t)}")
            return t
        except Exception:
            logger.info("Failed to get access token with Gen3Auth")
            raise

    def _get_s3_client(
        self, access_token: str, s3_storage_config: WorkflowStorageConfig
    ):
        """Creates and returns an S3 client."""
        print("self.S3_ENDPOINT_URL =", self.S3_ENDPOINT_URL)
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
        logger.info(
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
            logger.info(f"S3 {action.upper()} response:  {response}")

        except botocore.exceptions.ClientError as e:
            logger.info("===================== Getting gen3-workflow logs...")
            cmd = [
                "kubectl",
                "-n",
                pytest.namespace,
                "logs",
                "-l",
                "app=gen3-workflow",
                "--tail",
                "300",
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                logger.info(f"success - {result.stdout.decode('utf-8')}")
            else:
                logger.info(
                    f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
                )

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
        except Exception as e:
            logger.info("===================== Getting gen3-workflow logs...")
            cmd = [
                "kubectl",
                "-n",
                pytest.namespace,
                "logs",
                "-l",
                "app=gen3-workflow",
                "--tail",
                "300",
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                logger.info(f"success - {result.stdout.decode('utf-8')}")
            else:
                logger.info(
                    f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
                )

            logger.error(f"Received an error from s3_client. Error: {e}")
            raise  # Reraise for other errors
        assert (
            response_status == expected_status
        ), f"Expected {expected_status}, got {response_status} when making an s3 request to perform {action} action on {bucket=} and {key=}. Response: {response}"
        return response

    def poll_until_task_reaches_expected_state(
        self, task_id, user, expected_final_state, max_retries=5, poll_interval=30
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
        for attempt in range(1, max_retries + 1):
            task_info = self.get_tes_task(
                task_id=task_id,
                user=user,
                expected_status=200,
            )
            state = task_info.get("state")

            if state == expected_final_state:
                logger.info(f"TES task reached final state '{state}'")
                return task_info

            assert (
                state not in final_states
            ), f"TES task reached a final state, that is not '{expected_final_state}'. Final state: {state}, Response: {task_info}"
            assert (
                state in transient_states
            ), f"Unexpected TES task state '{state}' encountered. Response: {task_info}"

            logger.info(
                f"Attempt {attempt} of {max_retries}: Task state is '{state}', retrying after {poll_interval} seconds..."
            )
            if attempt <= max_retries:
                time.sleep(poll_interval)

        logger.info("===================== kubectl get priorityclass")
        cmd = [
            "kubectl",
            "get",
            "priorityclass",
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            logger.info(f"success - {result.stdout.decode('utf-8')}")
        else:
            logger.info(
                f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
            )

        # logger.info("===================== kubectl get nodepool")
        # cmd = [
        #     "kubectl",
        #     "get",
        #     "nodepool",
        # ]
        # result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # if result.returncode == 0:
        #     logger.info(f"success - {result.stdout.decode('utf-8')}")
        # else:
        #     logger.info(
        #         f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
        #     )

        # logger.info("===================== kubectl get node")
        # cmd = [
        #     "kubectl",
        #     "get",
        #     "node",
        # ]
        # result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # if result.returncode == 0:
        #     logger.info(f"success - {result.stdout.decode('utf-8')}")
        # else:
        #     logger.info(
        #         f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
        #     )

        logger.info(
            "===================== kubectl get pod -n workflow-pods-funnel-pr-1"
        )
        cmd = [
            "kubectl",
            "get",
            "pod",
            "-n",
            "workflow-pods-funnel-pr-1",
            "-o",
            "name",
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            logger.info(f"success - {result.stdout.decode('utf-8')}")
        else:
            logger.info(
                f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
            )

        pods = [p for p in result.stdout.decode("utf-8").split("\n") if p]
        logger.info(
            f"===================== kubectl get pod -n workflow-pods-funnel-pr-1: {pods}"
        )
        for pod in pods:
            logger.info(f"===================== kubectl describe pod {pod}")
            cmd = [
                "kubectl",
                "describe",
                pod,
                "-n",
                "workflow-pods-funnel-pr-1",
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                logger.info(f"success - {result.stdout.decode('utf-8')}")
            else:
                logger.info(
                    f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
                )

        logger.info("===================== kubectl get pod -n mount-s3")
        cmd = [
            "kubectl",
            "get",
            "pod",
            "-n",
            "mount-s3",
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            logger.info(f"success - {result.stdout.decode('utf-8')}")
        else:
            logger.info(
                f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
            )

        logger.info("===================== kubectl get pod -n mount-s3 -o name")
        cmd = [
            "kubectl",
            "get",
            "pod",
            "-n",
            "mount-s3",
            "-o",
            "name",
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            logger.info(f"success - {result.stdout.decode('utf-8')}")
        else:
            logger.info(
                f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
            )

        pods = [p for p in result.stdout.decode("utf-8").split("\n") if p]
        logger.info(f"===================== kubectl get pod -n mount-s3: {pods}")
        for pod in pods:
            logger.info(f"===================== kubectl logs {pod}")
            cmd = [
                "kubectl",
                "logs",
                pod,
                "-n",
                "mount-s3",
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                logger.info(f"success - {result.stdout.decode('utf-8')}")
            else:
                logger.info(
                    f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
                )
        for pod in pods:
            logger.info(f"===================== kubectl describe pod {pod}")
            cmd = [
                "kubectl",
                "describe",
                pod,
                "-n",
                "mount-s3",
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                logger.info(f"success - {result.stdout.decode('utf-8')}")
            else:
                logger.info(
                    f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
                )

            try:
                cmd = f"kubectl exec -n mount-s3 {pod} -- env"
                logger.info(f"===================== {cmd}")
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    text=True,
                )
                if result.returncode == 0:
                    logger.info(f"success - {result.stdout}")
                else:
                    logger.info(f"failure - {result.returncode} - {result.stderr}")
            except Exception as e:
                print(e)

            try:
                cmd = (
                    f'kubectl get -n mount-s3 {pod} -o yaml | grep -A 50 "containers:"'
                )
                logger.info(f"===================== {cmd}")
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    text=True,
                )
                if result.returncode == 0:
                    logger.info(f"success - {result.stdout}")
                else:
                    logger.info(f"failure - {result.returncode} - {result.stderr}")
            except Exception as e:
                print(e)

            try:
                cmd = f"kubectl get -n mount-s3 {pod} -o yaml | grep -A 30 env"
                logger.info(f"===================== {cmd}")
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    text=True,
                )
                if result.returncode == 0:
                    logger.info(f"success - {result.stdout}")
                else:
                    logger.info(f"failure - {result.returncode} - {result.stderr}")
            except Exception as e:
                print(e)

        try:
            logger.info(
                "===================== kubectl get pv -n workflow-pods-funnel-pr-1 -l app=funnel"
            )
            cmd = [
                "kubectl",
                "get",
                "pv",
                "-n",
                "workflow-pods-funnel-pr-1",
                "-l",
                "app=funnel",
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                logger.info(f"success - {result.stdout.decode('utf-8')}")
            else:
                logger.info(
                    f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
                )
        except Exception as e:
            print(e)

        try:
            cmd = "kubectl get pv -n workflow-pods-funnel-pr-1 -l app=funnel -o yaml | grep -A 30 mountOptions"
            logger.info(f"===================== {cmd}")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                text=True,
            )
            if result.returncode == 0:
                logger.info(f"success - {result.stdout}")
            else:
                logger.info(f"failure - {result.returncode} - {result.stderr}")
        except Exception as e:
            print(e)

        try:
            # kubectl run -it --rm debug -n mount-s3 --image=curlimages/curl --restart=Never \
            #   --overrides='{
            #     "spec": {
            #       "containers": [{
            #         "name": "debug",
            #         "image": "curlimages/curl",
            #         "args": ["curl", "-v", "http://minio.funnel-pr-1.svc.cluster.local:9000/minio/health/live"],
            #         "securityContext": {
            #           "allowPrivilegeEscalation": false,
            #           "runAsNonRoot": true,
            #           "runAsUser": 1000,
            #           "capabilities": {"drop": ["ALL"]},
            #           "seccompProfile": {"type": "RuntimeDefault"}
            #         }
            #       }],
            #       "restartPolicy": "Never"
            #     }
            #   }'

            # kubectl run -it --rm debug -n funnel-pr-1 --image=curlimages/curl --restart=Never -- \
            #   curl -v http://minio.funnel-pr-1.svc.cluster.local:9000/minio/health/live
            cmd = "kubectl run -it --rm debug -n mount-s3 --image=curlimages/curl --restart=Never -- curl -v http://minio.funnel-pr-1.svc.cluster.local:9000/minio/health/live"
            logger.info(f"===================== {cmd}")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                text=True,
            )
            if result.returncode == 0:
                logger.info(f"success - {result.stdout}")
            else:
                logger.info(f"failure - {result.returncode} - {result.stderr}")
        except Exception as e:
            print(e)

        raise Exception(
            f"TES task did not reach a final state in time. Last known state: {state}, Response: {task_info}"
        )

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

        logger.info("===================== Getting gen3-workflow logs...")
        cmd = [
            "kubectl",
            "-n",
            pytest.namespace,
            "logs",
            "-l",
            "app=gen3-workflow",
            "--tail",
            "300",
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            logger.info(f"success - {result.stdout.decode('utf-8')}")
        else:
            logger.info(
                f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
            )

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

        # def get_keys_url(issuer, force_issuer=None):
        #     """
        #     Prefer OIDC discovery doc, but fall back on Fence-specific /jwt/keys for backwards compatibility (or if `force_issuer` is True)
        #     """
        #     jwt_keys_url = "/".join([issuer.strip("/"), "jwt", "keys"])
        #     logger.info(f"jwt_keys_url = {jwt_keys_url}")
        #     if force_issuer:
        #         return jwt_keys_url

        #     openid_cfg_path = "/".join(
        #         [issuer.strip("/"), ".well-known", "openid-configuration"]
        #     )
        #     logger.info(f"openid_cfg_path = {openid_cfg_path}")
        #     try:
        #         r = requests.get(openid_cfg_path)
        #         logger.info(f"r = {r.status_code} {r.text}")
        #         jwks_uri = r.json().get("jwks_uri", "")
        #         logger.info(f"jwks_uri = {jwks_uri}")
        #         return jwks_uri
        #     except Exception:
        #         logger.info(f"returning jwt_keys_url = {jwt_keys_url}")
        #         return jwt_keys_url

        # logger.info("===================== Reproduce error...")
        # issuer = "http://fence.funnel-pr-1.svc.cluster.local/user"
        # force_issuer = None
        # try:
        #     u = get_keys_url(issuer, force_issuer)
        #     logger.info(f"keys url = {u}")
        #     resp = requests.get(u)
        #     logger.info(f"resp = {resp.status_code} {resp.text}")
        #     resp.raise_for_status()
        #     print(resp.json())
        # except Exception as e:
        #     print("Cannot fetch pubkey from issuer {}: {}".format(issuer, str(e)))

        # url = "http://localhost:8000/user/.well-known/openid-configuration"
        # r = requests.get(url)
        # logger.info(f"{url}, {r.status_code}, {r.text}")

        ######################################################

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

        # logger.info("===================== Getting gen3-workflow logs...")
        # cmd = [
        #     "kubectl",
        #     "-n",
        #     pytest.namespace,
        #     "logs",
        #     "-l",
        #     "app=gen3-workflow",
        #     "--tail",
        #     "300",
        # ]
        # result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # if result.returncode == 0:
        #     logger.info(f"success - {result.stdout.decode('utf-8')}")
        # else:
        #     logger.info(
        #         f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
        #     )

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
            logger.info("===================== Getting gen3-workflow logs...")
            cmd = [
                "kubectl",
                "-n",
                pytest.namespace,
                "logs",
                "-l",
                "app=gen3-workflow",
                "--tail",
                "300",
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                logger.info(f"success - {result.stdout.decode('utf-8')}")
            else:
                logger.info(
                    f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
                )

            logger.info("===================== Getting arborist logs...")
            cmd = [
                "kubectl",
                "-n",
                pytest.namespace,
                "logs",
                "-l",
                "app=arborist",
                "--tail",
                "300",
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                logger.info(f"success - {result.stdout.decode('utf-8')}")
            else:
                logger.info(
                    f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
                )

            logger.info("===================== Getting useryaml logs...")
            cmd = [
                "kubectl",
                "-n",
                pytest.namespace,
                "logs",
                "-l",
                "job-name=useryaml",
                "--tail",
                "300",
                "--all-containers",
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                logger.info(f"success - {result.stdout.decode('utf-8')}")
            else:
                logger.info(
                    f"failure - {result.returncode} - {result.stderr.decode('utf-8')}"
                )

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
        tes_task_url = f"{self.TES_URL}/tasks/{task_id}"

        response = requests.get(
            url=tes_task_url,
            headers={"Authorization": f"bearer {access_token}"} if user else {},
        )
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
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status}, got {response.status_code} when attempting to make an POST request to {tes_task_url}: {response.text}"
        return response.json()

    def run_nextflow_task(
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
            assert (
                execution.status == "OK"
            ), f"Nextflow workflow execution failed with status: {execution.status} and log:\n{log_file_content}"

            return log_file_content
        finally:
            # Change back to the original working directory
            os.chdir(original_cwd)
