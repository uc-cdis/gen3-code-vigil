import os
import pytest
import requests

from cdislogging import get_logger

from gen3.auth import Gen3Auth

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class ManifestService(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/manifests/"

    def post_manifest_for_user(self, user: str, data: list):
        """
        Create manifest for user
        user - pick one from conftest.py - main_account / indexing_account / auxAcct1_account /
            auxAcct2_account / user0_account
        """
        logger.info(f"Posting manifest for user {user} with data {data}")
        res = requests.post(
            self.BASE_URL, json=data, auth=Gen3Auth(refresh_token=pytest.api_keys[user])
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
        res = requests.get(
            self.BASE_URL, auth=Gen3Auth(refresh_token=pytest.api_keys[user])
        )
        logger.info(res.text)
        return res.text
