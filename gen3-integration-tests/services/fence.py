import json
import os
import pytest
import requests

from cdislogging import get_logger
from gen3.auth import Gen3Auth

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Fence(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/user"
        self.API_CREDENTIALS_ENDPOINT = f"{self.BASE_URL}/credentials/api"
        self.OAUTH_TOKEN_ENDPOINT = f"{self.BASE_URL}/oauth2/token"
        self.USER_ENDPOINT = f"{self.BASE_URL}/user"

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

    def createSignedUrl(self, id, user, expectedStatus, file_type, params=[]):
        API_GET_FILE = "/data/download"
        url = API_GET_FILE + "/" + str(id)
        if len(params) > 0:
            url = url + "?" + "&".join(params)
        if user:
            auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
            response = auth.curl(path=url)
        else:
            # Perform GET requests without authorization code
            response = requests.get(self.BASE_URL + url, auth={})
        logger.info(str(file_type) + " status code : " + str(response.status_code))
        assert expectedStatus == response.status_code
        return True

    def getUserInfo(self, user="main_account"):
        """Get user info"""
        user_info_response = requests.get(
            f"{self.USER_ENDPOINT}", headers=pytest.auth_headers[user]
        )
        response_data = user_info_response.json()
        logger.debug(f"User info {response_data}")
        return response_data
