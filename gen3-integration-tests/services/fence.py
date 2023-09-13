import json
import pytest
import requests


class Fence(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/user"
        self.API_CREDENTIALS_ENDPOINT = f"{self.BASE_URL}/credentials/api"

    def get_access_token(self, api_key):
        res = requests.post(
            f"{self.API_CREDENTIALS_ENDPOINT}/access_token",
            data=json.dumps({"api_key": api_key}),
        )
        if res.status_code == 200:
            return res.json()["access_token"]
        else:
            raise Exception("Failed to get access token")
