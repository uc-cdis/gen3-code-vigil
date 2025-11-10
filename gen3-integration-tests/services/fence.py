import base64
import json

import pytest
import requests
from gen3.auth import Gen3Auth, Gen3AuthError
from pages.login import LoginPage
from pages.user_register import UserRegister
from playwright.sync_api import Page
from utils import logger
from utils.misc import retry
from utils.test_execution import screenshot


class Fence(object):
    def __init__(self):
        # Endpoints
        self.BASE_URL = f"{pytest.root_url}/user"
        self.API_CREDENTIALS_ENDPOINT = "/credentials/api"
        self.OAUTH_TOKEN_ENDPOINT = "/oauth2/token"
        self.DATA_UPLOAD_ENDPOINT = "/data/upload"
        self.DATA_ENDPOINT = "/data"
        self.DATA_DOWNLOAD_ENDPOINT = "/data/download"
        self.USER_ENDPOINT = "/user"
        self.VERSION_ENDPOINT = "/_version"
        self.AUTHORIZE_OAUTH2_CLIENT_ENDPOINT = "/oauth2/authorize"
        self.TOKEN_OAUTH2_CLIENT_ENDPOINT = "/oauth2/token"
        self.MULTIPART_UPLOAD_INIT_ENDPOINT = "/data/multipart/init"
        self.MULTIPART_UPLOAD_ENDPOINT = "/data/multipart/upload"
        self.MULTIPART_UPLOAD_COMPLETE_ENDPOINT = "/data/multipart/complete"
        self.GOOGLE_SA_KEYS_ENDPOINT = "/credentials/google/"
        # Locators
        self.CONSENT_AUTHORIZE_BUTTON = "//button[@id='yes']"
        self.CONSENT_CANCEL_BUTTON = "//button[@id='no']"
        self.USERNAME_LOCATOR = "//div[@class='top-bar']//a[3]"
        self.CONSENT_CODE_ERROR_TEXT = "//div[@class='error-page__status-code-text']/h2"

    @retry(
        times=3,
        delay=20,
        exceptions=(
            AssertionError,
            Gen3AuthError,
        ),
    )
    def create_signed_url(
        self, id, user, expected_status, params=[], access_token=None
    ):
        """Creates a signed url for the requested id"""
        API_GET_FILE = self.DATA_DOWNLOAD_ENDPOINT
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
        assert (
            expected_status == response.status_code
        ), f"Expected response {expected_status}, but got {response.status_code}"
        if response.status_code == 200:
            return response.json()
        return response

    def get_url_for_data_upload(self, file_name: str, user: str) -> dict:
        """Generate the url for uploading the data"""
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        headers = {
            "Content-Type": "application/json",
        }
        response = requests.post(
            url=f"{self.BASE_URL}{self.DATA_UPLOAD_ENDPOINT}",
            data=json.dumps({"file_name": file_name}),
            auth=auth,
            headers=headers,
        )
        return response

    def get_url_for_data_upload_for_existing_file(self, guid: str, user: str) -> dict:
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        response = auth.curl(path=f"{self.DATA_UPLOAD_ENDPOINT}/{guid}")
        return response

    @retry(times=6, delay=20, exceptions=(AssertionError,))
    def get_file(self, url: str) -> str:
        """Gets the file content from the presigned url"""
        response = requests.get(url=url)
        assert (
            response.status_code == 200
        ), f"Expected response was 200 but got {response.status_code}"
        return response.content.decode()

    def check_file_equals(self, signed_url_res: dict, file_content: str):
        """Gets the file file content and matches with the expected value"""
        assert "url" in signed_url_res.keys(), f"URL key is missing.\n{signed_url_res}"
        contents = self.get_file(signed_url_res["url"])
        assert (
            contents == file_content
        ), f"Data don't match.\n{contents}\n{file_content}"

    def delete_file(self, guid: str, user: str) -> int:
        """Deletes the file based on guid"""
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        url = f"{self.BASE_URL}{self.DATA_ENDPOINT}/{guid}"
        response = requests.delete(url=url, auth=auth)
        return response.status_code

    def get_user_info(
        self, user: str = "main_account", access_token=None, expected_status=200
    ):
        """Get user info"""
        if access_token:
            user_info_response = requests.get(
                f"{self.BASE_URL}{self.USER_ENDPOINT}",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"bearer {access_token}",
                },
            )
        else:
            auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
            access_token = auth.get_access_token()
            user_info_response = auth.curl(path=f"{self.USER_ENDPOINT}")
        assert (
            user_info_response.status_code == expected_status
        ), f"Expected status {expected_status} but got {user_info_response.status_code}"
        response_data = user_info_response.json()
        logger.debug(f"User info {response_data}")
        return response_data

    def get_user_tokens_with_client(
        self,
        page: Page,
        client_id: str,
        client_secret: str,
        user="main_account",
        scopes=(
            "openid+user+data+google_credentials+google_service_account+google_link"
        ),
    ):
        """Gets the user token for a given client"""
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
        return response

    def get_consent_code(
        self,
        page: Page,
        client_id,
        response_type,
        scopes,
        consent="ok",
        expect_code=True,
        client_email_id="basictestclient@example.org",
    ):
        """Gets the consent code"""
        url = f"{self.BASE_URL}{self.AUTHORIZE_OAUTH2_CLIENT_ENDPOINT}?response_type={response_type}&client_id={client_id}&redirect_uri={f'{pytest.root_url}'}&scope={scopes}"
        page.goto(url)
        page.wait_for_load_state("load")
        current_url = page.url
        if "/user/register" in current_url:
            logger.info(f"Registering User {client_email_id}")
            user_register = UserRegister()
            user_register.register_user(page, user_email=client_email_id)
        if expect_code:
            if consent == "cancel":
                page.locator(self.CONSENT_CANCEL_BUTTON).click()
            else:
                page.locator(self.CONSENT_AUTHORIZE_BUTTON).click()
            page.wait_for_selector(self.USERNAME_LOCATOR, state="attached")
        else:
            text_from_page = page.locator(self.CONSENT_CODE_ERROR_TEXT).text_content()
            assert text_from_page in [
                "Unauthorized",
                "Bad Request",
            ], f"Expected Unauthorized or Bad Request, instead got {text_from_page}"
        return page.url

    def get_token_with_auth_code(self, client_id, client_secret, code, grant_type):
        """Gets the access token with authroization code"""
        url = f"{self.BASE_URL}{self.TOKEN_OAUTH2_CLIENT_ENDPOINT}?code={code}&grant_type={grant_type}&redirect_uri=https%3A%2F%2F{pytest.hostname}"
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

    def assert_token_response(
        self, response, expected_status_code=200, validate_keys=True
    ):
        """Validates the token properties for a given api response/request"""
        assert (
            response.status_code == expected_status_code
        ), f"Expected status code 200 but got {response.status_code}"
        if validate_keys:
            for key in ["access_token", "expires_in", "id_token", "refresh_token"]:
                assert key in response.json(), f"{key} is missing in {response['data']}"

    def get_tokens_implicit_flow(
        self,
        page,
        client_id,
        response_type,
        scopes,
        consent="yes",
        expect_token=True,
        client_email_id="implicittestclient@example.org",
    ):
        """Gets the token from the UI"""
        url = f"{self.BASE_URL}{self.AUTHORIZE_OAUTH2_CLIENT_ENDPOINT}?response_type={response_type}&client_id={client_id}&redirect_uri=https://{pytest.hostname}&scope={scopes}&nonce=n-0S6_WzA2Mj"
        page.goto(url)
        page.wait_for_load_state("load")
        current_url = page.url
        if "/user/register" in current_url:
            logger.info(f"Registering User {client_email_id}")
            user_register = UserRegister()
            user_register.register_user(page, user_email=client_email_id)
        if expect_token:
            if page.locator(self.CONSENT_AUTHORIZE_BUTTON).is_visible():
                if consent == "cancel":
                    page.locator(self.CONSENT_CANCEL_BUTTON).click()
                else:
                    page.locator(self.CONSENT_AUTHORIZE_BUTTON).click()
                page.wait_for_selector(self.USERNAME_LOCATOR, state="attached")
        else:
            text_from_page = page.locator(self.CONSENT_CODE_ERROR_TEXT).text_content()
            assert (
                text_from_page == "Unauthorized"
            ), f"Expected Unauthorized, instead got {text_from_page}"
        screenshot(page, "GetTokensImplicitFlow")
        return page.url

    def initialize_multipart_upload(self, file_name, user):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        headers = {
            "Content-Type": "application/json",
        }
        response = requests.post(
            url=f"{self.BASE_URL}{self.MULTIPART_UPLOAD_INIT_ENDPOINT}",
            data=json.dumps({"file_name": file_name}),
            auth=auth,
            headers=headers,
        )
        assert (
            response.status_code == 201
        ), f"Expected status 201 but got {response.status_code}"
        return response.json()

    def get_url_for_multipart_upload(self, key, upload_id, part_number, user):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        headers = {
            "Content-Type": "application/json",
        }
        response = requests.post(
            url=f"{self.BASE_URL}{self.MULTIPART_UPLOAD_ENDPOINT}",
            data=json.dumps(
                {"key": key, "uploadId": upload_id, "partNumber": part_number}
            ),
            auth=auth,
            headers=headers,
        )
        assert (
            response.status_code == 200
        ), f"Expected status 200 but got {response.status_code}"
        return response.json()

    def complete_multipart_upload(self, key, upload_id, parts, user):
        headers = {
            "Content-Type": "application/json",
        }
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        response = requests.post(
            url=f"{self.BASE_URL}{self.MULTIPART_UPLOAD_COMPLETE_ENDPOINT}",
            data=json.dumps({"key": key, "uploadId": upload_id, "parts": parts}),
            auth=auth,
            headers=headers,
        )
        return response.status_code

    def upload_file_using_presigned_url(self, presigned_url, file_data, file_size):
        headers = {"Content-Length": str(file_size)}
        if isinstance(file_data, dict):
            response = requests.put(url=presigned_url, data=file_data, headers=headers)
        else:
            response = requests.put(
                url=presigned_url, data=open(file_data, "rb"), headers=headers
            )
        assert (
            response.status_code == 200
        ), f"Upload to S3 didn't happen properly. Status code : {response.status_code}"

    def upload_data_using_presigned_url(self, presigned_url, file_data):
        response = requests.put(url=presigned_url, data=file_data)
        assert (
            response.status_code == 200
        ), f"Upload to S3 didn't happen properly. Status code : {response.status_code}"
        return response.headers["ETag"].strip('"')

    @retry(times=10, delay=30, exceptions=(AssertionError))
    def wait_upload_file_updated_from_indexd_listener(self, indexd, file_node):
        response = indexd.get_record(file_node.did)
        indexd.file_equals(res=response, file_record=file_node)
        return response

    def create_api_key(self, scope, page, token=None):
        login_page = LoginPage()
        if not token:
            # Login with main_account user and get the access_token
            logger.info("Logging in with mainAcct")
            login_page.go_to(page)
            token = login_page.login(page)["value"]
        data = {
            "scope": scope,
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"bearer {token}",
        }
        res = requests.post(
            url=f"{self.BASE_URL}{self.API_CREDENTIALS_ENDPOINT}/",
            json=data,
            headers=headers,
        )
        return res, token

    def delete_api_key(self, api_key, token, page):
        login_page = LoginPage()
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"bearer {token}",
        }
        res = requests.delete(
            url=f"{self.BASE_URL}{self.API_CREDENTIALS_ENDPOINT}/{api_key}",
            headers=headers,
        )
        assert (
            res.status_code == 204
        ), f"Expected status code 204 but got {res.status_code}"
        login_page.logout(page)

    def get_version(self, user="main_account"):
        """Get fence version"""
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        response = auth.curl(path=f"{self.VERSION_ENDPOINT}")
        assert (
            response.status_code == 200
        ), f"Expected status code 200 but got {response.status_code}"
        assert "version" in response.json().keys()
        return response.json()["version"]

    def get_google_sa_keys(self, page, user="main_account"):
        """Get the Google SA keys for given user"""
        # Token returned from API key doesnt have Google scope, so login from UI
        login_page = LoginPage()
        login_page.go_to(page)
        token = login_page.login(page, user=user)["value"]
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"bearer {token}",
        }
        response = requests.get(
            f"{self.BASE_URL}{self.GOOGLE_SA_KEYS_ENDPOINT}", headers=headers
        )
        return response.json()["access_keys"], token

    def delete_google_sa_keys(self, page, user="main_account"):
        """Deletes the Google SA keys for given user"""
        list_sa_keys, token = self.get_google_sa_keys(page=page, user=user)
        headers = {
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
        }
        for key_item in list_sa_keys:
            sa_key = key_item["name"].split("/")[-1]
            delete_resp = requests.delete(
                f"{self.BASE_URL}/{self.GOOGLE_SA_KEYS_ENDPOINT}/{sa_key}",
                headers=headers,
            )
            logger.info(
                f"Deleted a key for {pytest.users[user]} and got response {delete_resp.status_code}"
            )
