import os
import pytest
import requests

from utils import logger

from gen3.auth import Gen3Auth


class ManifestService(object):
    def __init__(self):
        self.BASE_ENDPOINT = "/manifests/"  # to be used in Gen3Auth
        self.BASE_URL = (
            f"{pytest.root_url}/{self.BASE_ENDPOINT}"  # to be used in requests
        )

    def post_manifest_for_user(self, user: str, data: list):
        """
        Create manifest for user
        user - pick one from conftest.py - main_account / indexing_account / auxAcct1_account /
            auxAcct2_account / user0_account
        """
        logger.info(f"Posting manifest for user {user} with data {data}")
        res = requests.post(
            f"{self.BASE_URL}",
            json=data,
            auth=Gen3Auth(refresh_token=pytest.api_keys[user]),
        )
        status = res.status_code
        resp = res.json()
        logger.info(f"{status} : {resp}")
        return (status, resp)

    def get_manifest_for_user(self, user: str):
        """
        Get manifests for a given user
        Returns the response text as a string
        """
        logger.info(f"Fetching manifest data for user {user}")
        auth = Gen3Auth(refresh_token=pytest.api_keys[user])
        res = auth.curl(self.BASE_ENDPOINT)
        logger.info(res.text)
        return res.text
