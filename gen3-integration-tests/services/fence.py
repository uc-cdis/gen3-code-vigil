import json
import os
import pytest
import requests

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Fence(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/user"
        self.API_CREDENTIALS_ENDPOINT = f"{self.BASE_URL}/credentials/api"

    def get_access_token(self, api_key):
        """Generate access token from api key"""
        res = requests.post(
            f"{self.API_CREDENTIALS_ENDPOINT}/access_token",
            data=json.dumps({"api_key": api_key}),
        )
        logger.info(f"Status code: {res.status_code}")
        if res.status_code == 200:
            return res.json()["access_token"]
        else:
            logger.info(f"Response: {res.text}")
            raise Exception(
                f"Failed to get access token from {self.API_CREDENTIALS_ENDPOINT}/access_token"
            )

    def createSignedUrl(self, id, useHeader, expectedStatus, file_type, params=[]):
        API_GET_FILE = f"{self.BASE_URL}/data/download"
        url = API_GET_FILE + "/" + str(id)
        if len(params) > 0:
            url = url + "?" + "&".join(params)
        response = requests.get(url=url, auth=useHeader)
        logger.info(str(file_type) + " status code : " + str(response.status_code))
        assert expectedStatus == response.status_code
        return True
