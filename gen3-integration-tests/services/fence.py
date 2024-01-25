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
        self.OAUTH_TOKEN_ENDPOINT = f"{self.BASE_URL}/oauth2/token"

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

    def get_access_token_header(access_token):
        return {
            "Accept": "application/json",
            "Authorization": f"bearer {access_token}",
        }

    def client_credentials_access_token(
        self, client_id, secret_id, expect_success=True
    ):
        """Generates access token with client credentials"""
        auth = (client_id, secret_id)
        data = {"grant_type": "client_credentials", "scope": "openid user"}

        res = requests.post(self.OAUTH_TOKEN_ENDPOINT, auth=auth, data=data)
        tokens_req = res.text
        tokens = json.loads(tokens_req)
        if expect_success:
            assert "access_token" in tokens, f"Cannot get access token: {tokens_req}"
        else:
            assert (
                "access_token" not in tokens
            ), f"Should not have been able to get access token"

        access_token = tokens.get("access_token", None)
        return access_token
