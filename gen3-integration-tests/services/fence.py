import json
import pytest
import requests
import base64
import os

from utils.misc import retry

from utils import logger
from pages.login import LoginPage
from gen3.auth import Gen3Auth
from playwright.sync_api import Page
from utils.test_execution import screenshot
from utils import TEST_DATA_PATH_OBJECT


class Fence(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/user"
        self.API_CREDENTIALS_ENDPOINT = "/credentials/api"
        self.OAUTH_TOKEN_ENDPOINT = "/oauth2/token"
        self.DATA_UPLOAD_ENDPOINT = "/data/upload"
        self.DATA_ENDPOINT = "/data"
        self.DATA_DOWNLOAD_ENDPOINT = "/data/download"
        self.USER_ENDPOINT = "/user"
        self.AUTHORIZE_OAUTH2_CLIENT_ENDPOINT = "/oauth2/authorize"
        self.TOKEN_OAUTH2_CLIENT_ENDPOINT = "/oauth2/token"
        self.MULTIPART_UPLOAD_INIT_ENDPOINT = "/data/multipart/init"
        self.MULTIPART_UPLOAD_ENDPOINT = "/data/multipart/upload"
        self.MULTIPART_UPLOAD_COMPLETE_ENDPOINT = "/data/multipart/complete"
        self.CONSENT_AUTHORIZE_BUTTON = "//button[@id='yes']"
        self.CONSENT_CANCEL_BUTTON = "//button[@id='no']"
        self.USERNAME_LOCATOR = "//div[@class='top-bar']//a[3]"
        self.CONSENT_CODE_ERROR_TEXT = "//div[@class='error-page__status-code-text']/h2"

    def create_signed_url(self, id, user, expectedStatus, params=[], access_token=None):
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
        assert response.status_code == 200
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
            user_info_response = requests.get(
                f"{self.BASE_URL}{self.USER_ENDPOINT}",
                headers=pytest.auth_headers[user],
            )
        assert user_info_response.status_code == expected_status
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
    ):
        """Gets the consent code"""
        url = f"{self.BASE_URL}{self.AUTHORIZE_OAUTH2_CLIENT_ENDPOINT}?response_type={response_type}&client_id={client_id}&redirect_uri={f'{pytest.root_url}'}&scope={scopes}"
        page.goto(url)
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
        self, page, client_id, response_type, scopes, consent="yes", expect_token=True
    ):
        """Gets the token from the UI"""
        url = f"{self.BASE_URL}{self.AUTHORIZE_OAUTH2_CLIENT_ENDPOINT}?response_type={response_type}&client_id={client_id}&redirect_uri=https://{pytest.hostname}&scope={scopes}&nonce=n-0S6_WzA2Mj"
        page.goto(url)
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

    def complete_mulitpart_upload(
        self, key, upload_id, parts, user, expected_status=200
    ):
        logger.info(parts)
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
        assert (
            response.status_code == expected_status
        ), f"Expected status 200 but got {response.status_code}"
        if expected_status != 200:
            return
        return response.json()

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

    @retry(times=12, delay=10, exceptions=(AssertionError))
    def wait_upload_file_updated_from_indexd_listener(self, indexd, file_node):
        response = indexd.get_record(file_node.did)
        indexd.file_equals(res=response, file_record=file_node)
        return response

    def get_user_info(self, user: str = "main_account"):
        """Get user info"""
        user_info_response = requests.get(
            f"{self.USER_ENDPOINT}", headers=pytest.auth_headers[user]
        )
        response_data = user_info_response.json()
        logger.debug(f"User info {response_data}")
        return response_data

    def create_api_key(self, scope, token):
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
        return res

    def delete_api_key(self, api_key, token):
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

    def get_client_id_secret(self, client_name):
        """Gets the fence client information from TEST_DATA_PATH_OBJECT/fence_client folder"""
        path = TEST_DATA_PATH_OBJECT / "fence_clients" / "clients_creds.txt"
        clients_dict = {}

        with open(path, "r") as file:
            for line in file:
                # Strip whitespace and skip empty lines
                line = line.strip()
                if not line:
                    continue

                # Split line into key and value
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()

                    clients_dict[key] = value
        assert (
            client_name in clients_dict.keys()
        ), f"{client_name} not found in {clients_dict.keys()}"
        client_info = clients_dict[client_name].split(",")
        client_id, client_secret = client_info[0], client_info[1]
        return client_id, client_secret
