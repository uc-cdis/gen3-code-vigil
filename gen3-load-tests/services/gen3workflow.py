"""
NOTE: Most of this logic is copy/pasted from gen3-integration-tests/services/gen3workflow.py
"""

from typing import Dict
from unittest.mock import patch

import pytest
import requests
from gen3.auth import (
    Gen3Auth,
    endpoint_from_token,
    remove_trailing_whitespace_and_slashes_in_url,
)
from utils import logger


@patch("gen3.auth.endpoint_from_token")
def _get_access_token(user: str = "main_account", endpoint_from_token_mock=None) -> str:
    """Helper function to retrieve an access token."""

    if not user:
        return None

    auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)

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
    if "localhost" in pytest.root_url:
        endpoint_from_token_mock.return_value = (
            remove_trailing_whitespace_and_slashes_in_url(pytest.root_url)
        )
    else:  # otherwise, no mocking
        endpoint_from_token_mock.side_effect = lambda arg: endpoint_from_token(arg)
    endpoint_from_token_mock.return_value = (
        remove_trailing_whitespace_and_slashes_in_url(pytest.root_url)
    )

    try:
        return auth.get_access_token()
    except Exception:
        logger.info("Failed to get access token with Gen3Auth")
        raise


def setup_storage(user: str = "main_account", expected_status=200) -> Dict:
    """Makes a GET request to the `/storage/setup` endpoint."""
    storage_url = f"{pytest.root_url}/workflows/storage/setup"
    headers = (
        {
            "Authorization": f"bearer {_get_access_token(user)}",
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
        f"{pytest.root_url}/workflows/storage/user-bucket"
        if delete_bucket
        else f"{pytest.root_url}/workflows/storage/user-bucket/objects"
    )
    headers = (
        {
            "Authorization": f"bearer {_get_access_token(user)}",
        }
        if user
        else {}
    )
    response = requests.delete(url=cleanup_url, headers=headers)

    # If ignore_missing is True, we allow 404 as a valid response status
    allowed_statuses = [expected_status, 404] if ignore_missing else [expected_status]
    assert (
        response.status_code in allowed_statuses
    ), f"Expected one of {allowed_statuses}, got {response.status_code} when making a DELETE request to {cleanup_url}: {response.text}"
