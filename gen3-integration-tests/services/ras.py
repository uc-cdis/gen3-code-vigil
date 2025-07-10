import os
import time

import pytest
import requests
from pages.login import LoginPage
from pages.user_register import UserRegister
from playwright.sync_api import Page, expect
from utils import logger
from utils.misc import retry
from utils.test_execution import screenshot


class RAS(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/user"
        self.RAS_REDIRECT_URI = f"{self.BASE_URL}/login/ras/callback"
        self.RAS_AUTH_ENDPOINT = f"{self.BASE_URL}/oauth2/authorize"
        self.RAS_TOKEN_ENDPOINT = f"{self.BASE_URL}/oauth2/token"
        self.USER_INFO_ENDPOINT = f"{self.BASE_URL}/openid/connect/v1.1/userinfo"

    def validate_creds(self, test_creds):
        creds_dict = {}
        for cred in test_creds:
            assert cred in os.environ, f"{cred} environment variable is missing"
            creds_dict[cred] = os.getenv(cred)
        return creds_dict

    def get_tokens(
        self,
        client_id: str,
        client_secret: str,
        scope: str,
        username: str,
        password: str,
        email: str,
        page: Page,
    ):
        auth_code = self.get_auth_code(
            scope, username, password, client_id, page=page, email=email
        )
        payload = f"grant_type=authorization_code&code={auth_code}&client_id={client_id}&client_secret={client_secret}&scope=openid user&redirect_uri={pytest.root_url}"
        get_ras_token = requests.post(
            url=self.RAS_TOKEN_ENDPOINT,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token_data = get_ras_token.json()
        return token_data

    @retry(times=3, delay=60, exceptions=(Exception))
    def get_auth_code(
        self,
        scope: str,
        username: str,
        password: str,
        client_id: str,
        email: str,
        page: Page,
    ):
        login = LoginPage()
        url = f"{self.RAS_AUTH_ENDPOINT}?response_type=code&client_id={client_id}&redirect_uri={pytest.root_url}&scope={scope}&idp=ras"
        page.goto(url)
        login.ras_login(page, username=username, password=password, portal_test=False)
        time.sleep(10)
        page.wait_for_load_state("load")
        current_url = page.url
        if "/user/register" in current_url:
            logger.info(f"Registering User {username}@perf.nih.gov")
            user_register = UserRegister()
            user_register.register_user(page, user_email=email)
        page.wait_for_load_state("load")
        authorize_button = page.locator(login.RAS_ACCEPT_AUTHORIZATION_BUTTON)
        if authorize_button.count() > 0:
            expect(authorize_button).to_be_enabled()
            logger.info("Clicking on authorization button")
            authorize_button.click()
            page.wait_for_load_state("load")
        screenshot(page, "RASCodePage")
        current_url = page.url
        assert "code=" in current_url, f"{current_url} is missing code= substring"
        code = current_url.split("code=")[-1]
        return code

    def get_token_from_refresh_token(
        self, refresh_token: str, client_id: str, client_secret: str, scope: str
    ):
        payload = f"grant_type=refresh_token&refresh_token={refresh_token}&client_id={client_id}&client_secret={client_secret}&scope={scope}"
        token_from_refresh = requests.post(
            url=self.RAS_TOKEN_ENDPOINT,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        token_from_refresh_json = token_from_refresh.json()
        return token_from_refresh_json

    def get_passport(self, access_token):
        get_passport_req = requests.get(
            url=self.USER_INFO_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"bearer {access_token}",
            },
        ).json()
        passport_body = get_passport_req["passwrt_jwt_v11"]
