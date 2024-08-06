import os
import requests
import time

from pages.login import LoginPage
from cdislogging import get_logger
from playwright.sync_api import Page

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class RAS(object):
    def __init__(self) -> None:
        self.RAS_SERVER_URL = "https://stsstg.nih.gov"
        self.RAS_REDIRECT_URI = "http://localhost:8080/user/login/ras/callback"
        self.RAS_AUTH_ENDPOINT = f"{self.RAS_SERVER_URL}/auth/oauth/v2/authorize"
        self.RAS_TOKEN_ENDPOINT = f"{self.RAS_SERVER_URL}/auth/oauth/v2/token"
        self.USER_INFO_ENDPOINT = f"{self.RAS_SERVER_URL}/openid/connect/v1.1/userinfo"

    def validate_creds(self, test_creds):
        creds_dict = {}
        for cred in test_creds:
            assert cred in os.environ, f"{cred} environment variable is missing"
            creds_dict[cred] = os.getenv(cred)
        return creds_dict

    def get_tokens(self, client_id, secret_id, scope, username, password, page: Page):
        auth_code = self.get_auth_code(scope, username, password, client_id, page)
        data = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "client_id": client_id,
            "client_secret": secret_id,
            "scope": scope,
            "redirect_uri": self.RAS_REDIRECT_URI,
        }
        logger.info(data)
        get_ras_token = requests.post(
            url=self.RAS_TOKEN_ENDPOINT,
            json=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ).json()
        logger.info(get_ras_token)
        return get_ras_token

    def get_auth_code(self, scope, username, password, client_id, page: Page):
        login = LoginPage()
        url = f"{self.RAS_AUTH_ENDPOINT}?response_type=code&client_id={client_id}&redirect_uri=http://localhost:8080/user/login/ras/callback&scope={scope}&idp=ras"
        logger.info(url)
        page.goto(url)
        login.ras_login(page, username=username, password=password)
        time.sleep(10)
        current_url = page.url
        assert "code=" in current_url, f"{current_url} is missing code= substring"
        code = current_url.split("code=")[-1]
        logger.info(code)
        return code

    def get_passport(self, access_token):
        get_passport_req = requests.get(
            url=self.USER_INFO_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"bearer {access_token}",
            },
        ).json()
        passport_body = get_passport_req["passwrt_jwt_v11"]

    def get_token_from_refresh_token(self, refresh_token, client_id, secret_id, scope):
        refresh_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": scope,
            "client_id": client_id,
            "client_secret": secret_id,
        }

        token_from_refresh = requests.post(
            url=self.RAS_TOKEN_ENDPOINT,
            json=refresh_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ).json()

        return token_from_refresh["access_token"]
