import json
import pytest
import requests
import base64

from utils.misc import retry

from utils import logger
from pages.login import LoginPage
from gen3.auth import Gen3Auth
from playwright.sync_api import Page


class Fence(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/user"
        self.API_CREDENTIALS_ENDPOINT = f"{self.BASE_URL}/credentials/api"
        self.OAUTH_TOKEN_ENDPOINT = f"{self.BASE_URL}/oauth2/token"
        self.DATA_UPLOAD_ENDPOINT = f"{self.BASE_URL}/data/upload"
        self.DATA_ENDPOINT = f"{self.BASE_URL}/data"
        self.USER_ENDPOINT = f"{self.BASE_URL}/user"
        self.AUTHORIZE_OAUTH2_CLIENT_ENDPOINT = f"{self.BASE_URL}/oauth2/authorize"
        self.TOKEN_OAUTH2_CLIENT_ENDPOINT = f"{self.BASE_URL}/oauth2/token"
        self.CONSENT_AUTHORIZE_BUTTON = "//button[@id='yes']"
        self.CONSENT_CANCEL_BUTTON = "//button[@id='no']"
        self.USERNAME_LOCATOR = "//div[@class='top-bar']//a[3]"

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

    def createSignedUrl(
        self, id, user, expectedStatus, file_type=None, params=[], access_token=None
    ):
        API_GET_FILE = "/data/download"
        url = API_GET_FILE + "/" + str(id)
        if len(params) > 0:
            url = url + "?" + "&".join(params)
        if user:
            auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
            response = auth.curl(path=url)
        elif access_token:
            response = requests.get(
                self.BASE_URL + url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"bearer {access_token}",
                },
            )
        else:
            # Perform GET requests without authorization code
            response = requests.get(self.BASE_URL + url, auth={})
        logger.info("Status code : " + str(response.status_code))
        assert expectedStatus == response.status_code
        if response.status_code == 200:
            return response.json()
        return response

    def get_url_for_data_upload(self, file_name: str, user: str) -> dict:
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        headers = {
            "Content-Type": "application/json",
        }
        response = requests.post(
            url=self.DATA_UPLOAD_ENDPOINT,
            data=json.dumps({"file_name": file_name}),
            auth=auth,
            headers=headers,
        )
        return response

    def has_url(self, response: dict) -> None:
        assert "url" in response.keys(), f"URL key is missing.\n{response}"

    def has_no_url(self, response: bytes) -> None:
        assert (
            "url" not in response.content.decode()
        ), f"URL key is missing.\n{response}"

    def get_file(self, url: str) -> str:
        response = requests.get(url=url)
        return response.content.decode()

    def check_file_equals(self, signed_url_res: dict, file_content: str):
        self.has_url(signed_url_res)
        contents = self.get_file(signed_url_res["url"])
        assert (
            contents == file_content
        ), f"Data don't match.\n{contents}\n{file_content}"

    def delete_file(self, guid: str, user: str) -> int:
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        url = f"{self.DATA_ENDPOINT}/{guid}"
        response = requests.delete(url=url, auth=auth)
        return response.status_code

    def upload_file_to_s3_using_presigned_url(
        self, presigned_url, file_path, file_size
    ):
        headers = {"Content-Length": str(file_size)}
        response = requests.put(
            url=presigned_url, data=open(file_path, "rb"), headers=headers
        )
        assert (
            response.status_code == 200
        ), f"Upload to S3 didn't happen properly. Status code : {response.status_code}"

    @retry(times=12, delay=10, exceptions=(AssertionError))
    def wait_upload_file_updated_from_indexd_listener(indexd, file_node):
        response = indexd.get_record(file_node.did)
        indexd.file_equals(res=response, file_node=file_node)
        return response

    def get_user_info(self, user: str = "main_account", access_token=None):
        """Get user info"""
        if access_token:
            user_info_response = requests.get(
                f"{self.USER_ENDPOINT}",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"bearer {access_token}",
                },
            )
        else:
            user_info_response = requests.get(
                f"{self.USER_ENDPOINT}", headers=pytest.auth_headers[user]
            )
        response_data = user_info_response.json()
        logger.debug(f"User info {response_data}")
        return response_data

    def get_user_tokens_with_client(
        self, page: Page, client_id: str, client_secret: str, user="main_account"
    ):
        scopes = (
            "openid+user+data+google_credentials+google_service_account+google_link"
        )
        login_page = LoginPage()
        logger.info("Logging in with mainAcct")
        login_page.go_to(page)
        login_page.login(page, user=user)

        url = self.get_consent_code(
            page=page, client_id=client_id, response_type="code", scopes=scopes
        )
        assert "code=" in url, f"{url} is missing code= substring"
        code = url.split("code=")[-1]
        response = self.get_token_with_auth_code(
            client_id, client_secret, code, "authorization_code"
        )
        return response.json()["access_token"]

    def get_consent_code(
        self,
        page: Page,
        client_id,
        response_type,
        scopes,
        consent="ok",
        expect_code=True,
    ):
        url = f"{self.AUTHORIZE_OAUTH2_CLIENT_ENDPOINT}?response_type={response_type}&client_id={client_id}&redirect_uri={f'{pytest.root_url}'}&scope={scopes}"
        page.goto(url)
        if expect_code:
            if consent == "cancel":
                page.locator(self.CONSENT_CANCEL_BUTTON).click()
            else:
                page.locator(self.CONSENT_AUTHORIZE_BUTTON).click()

        page.wait_for_selector(self.USERNAME_LOCATOR, state="attached")
        return page.url

    def get_token_with_auth_code(self, client_id, client_secret, code, grant_type):
        url = f"{self.TOKEN_OAUTH2_CLIENT_ENDPOINT}?code={code}&grant_type={grant_type}&redirect_uri=https%3A%2F%2F{pytest.hostname}"
        data = {
            "client_id": f"{client_id}",
            "client_secret": f"{client_secret}",
        }
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth}",
        }
        response = requests.post(url=url, data=json.dumps(data), headers=headers)
        return response
