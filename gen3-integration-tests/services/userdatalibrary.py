import pytest
import requests
from gen3.auth import Gen3Auth
from utils import logger


class UserDataLibrary(object):
    def __init__(self):
        self.BASE_ENDPOINT = "/library"
        self.LISTS_ENDPOINT = f"{self.BASE_ENDPOINT}/lists"

    def create_list(self, user, data, expected_status=201):
        """helper function to create list in data library"""
        logger.info("Creating Data Library List")
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        url = f"{pytest.root_url}/{self.LISTS_ENDPOINT}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth.get_access_token()}",
        }
        response = requests.put(
            url,
            json=data,
            headers=headers,
        )
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status} status but got {response.status_code}"
        if response.status_code == 201:
            return response.json()

    def read_list(self, user, list_id=None, expected_status=200):
        """
        helper function to read list in data library
        reads all lists if list_id is not passed
        """
        logger.info("Reading Data Library List")
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        if list_id:
            url = f"{self.LISTS_ENDPOINT}/{list_id}"
        else:
            # All lists
            url = f"{self.LISTS_ENDPOINT}"
        logger.info(url)
        response = auth.curl(path=url)
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status} status but got {response.status_code}"
        return response.json()

    def update_list(self, user, list_id, data, expected_status=200):
        """helper function to update list in data library"""
        logger.info("Updating Data Library List")
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        headers = {
            "Authorization": f"bearer {auth.get_access_token()}",
            "Content-Type": "application/json",
        }
        url = f"{pytest.root_url}/{self.LISTS_ENDPOINT}/{list_id}"
        response = requests.put(
            url,
            json=data,
            headers=headers,
        )
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status} status but got {response.status_code}"
        return response.json()

    def delete_list(self, user, list_id=None, expected_status=204):
        """
        helper function to delete list in data library
        deletes all lists if list_id is None
        """
        logger.info("Deleting Data Library List")
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        if list_id:
            url = f"{pytest.root_url}/{self.LISTS_ENDPOINT}/{list_id}"
        else:
            # Delete all lists
            url = f"{pytest.root_url}/{self.LISTS_ENDPOINT}"
        headers = {
            "Authorization": f"bearer {auth.get_access_token()}",
        }
        response = requests.delete(
            url,
            headers=headers,
        )
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status} status but got {response.status_code}"
