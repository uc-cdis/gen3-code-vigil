"""
NOTE: Most of this logic is copy/pasted from gen3-integration-tests/services/gen3workflow.py
"""

from typing import Dict

import pytest
import requests
from services.fence import Fence


class Gen3Workflow:
    def __init__(self):
        self.fence = Fence()
        self.BASE_URL = pytest.root_url
        # `SERVICE_URL` is only used for endpoints that do NOT require DPoP; the rest go through
        # the Gen3 SDK's DPoP proxy
        self.SERVICE_URL = "/workflows"

    def setup_storage(self, user: str = "main_account", expected_status=200) -> Dict:
        """Makes a GET request to the `/storage/setup` endpoint."""
        with self.fence.get_token_and_gen3_url(user, suffix=self.SERVICE_URL) as (
            access_token,
            url,
        ):
            storage_url = f"{url}/storage/setup"
            headers = (
                {
                    "Authorization": f"bearer {access_token}",
                }
                if user
                else {}
            )
            response = requests.get(url=storage_url, headers=headers)
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
        with self.fence.get_token_and_gen3_url(user, suffix=self.SERVICE_URL) as (
            access_token,
            url,
        ):
            cleanup_url = (
                f"{url}/storage/user-bucket"
                if delete_bucket
                else f"{url}/storage/user-bucket/objects"
            )
            headers = (
                {
                    "Authorization": f"bearer {access_token}",
                }
                if user
                else {}
            )
            response = requests.delete(url=cleanup_url, headers=headers)

        # If ignore_missing is True, we allow 404 as a valid response status
        allowed_statuses = (
            [expected_status, 404] if ignore_missing else [expected_status]
        )
        assert (
            response.status_code in allowed_statuses
        ), f"Expected one of {allowed_statuses}, got {response.status_code} when making a DELETE request to {cleanup_url}: {response.text}"
