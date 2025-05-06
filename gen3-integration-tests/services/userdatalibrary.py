import json

import pytest
import requests
from gen3.auth import Gen3Auth
from utils import logger


class UserDataLibrary(object):
    def __init__(self):
        self.BASE_ENDPOINT = f"{pytest.root_url}"
        self.LIBRARY_LISTS_ENDPOINT = "/library/lists"

    def create_list(self, user, data, expected_status=201):
        """helper function to create list in data library"""
        logger.info("Creating Data Library List")
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        url = self.BASE_ENDPOINT + self.LIBRARY_LISTS_ENDPOINT
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
        ), f"Expected {expected_status} status but for {response.status_code}"
        if response.status_code == 201:
            return response.json()

    def read_list(self, user, list_id, expected_status=200):
        """helper function to read list in data library"""
        logger.info("Reading Data Library List")
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        url = self.LIBRARY_LISTS_ENDPOINT + f"/{list_id}"
        logger.info(url)
        response = auth.curl(path=url)
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status} status but for {response.status_code}"
        return response.json()

    def read_all_lists(self, user, expected_status=200):
        """helper function to read all lists in data library"""
        logger.info("Reading All Data Library Lists")
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        response = auth.curl(path=self.LIBRARY_LISTS_ENDPOINT)
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status} status but for {response.status_code}"
        return response.json()

    def update_list(self, user, list_id, data, expected_status=200):
        """helper function to update list in data library"""
        logger.info("Updating Data Library List")
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        headers = {
            "Authorization": f"bearer {auth.get_access_token()}",
            "Content-Type": "application/json",
        }
        url = self.BASE_ENDPOINT + self.LIBRARY_LISTS_ENDPOINT + f"/{list_id}"
        response = requests.put(
            url,
            json=data,
            headers=headers,
        )
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status} status but for {response.status_code}"
        return response.json()

    def delete_list(self, user, list_id, expected_status=204):
        """helper function to delete list in data library"""
        logger.info("Deleting Data Library List")
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        url = self.BASE_ENDPOINT + self.LIBRARY_LISTS_ENDPOINT + f"/{list_id}"
        headers = {
            "Authorization": f"bearer {auth.get_access_token()}",
        }
        response = requests.delete(
            url,
            headers=headers,
        )
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status} status but for {response.status_code}"

    def delete_all_lists(self, user, expected_status=204):
        """helper function to delete all lists in data library"""
        logger.info("Deleting All Data Library Lists")
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        url = self.BASE_ENDPOINT + self.LIBRARY_LISTS_ENDPOINT
        headers = {
            "Authorization": f"bearer {auth.get_access_token()}",
        }
        response = requests.delete(
            url,
            headers=headers,
        )
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status} status but for {response.status_code}"
