import json
import os
import pytest
import requests

from utils.misc import retry

from cdislogging import get_logger
from gen3.auth import Gen3Auth

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Fence(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/user"
        self.API_CREDENTIALS_ENDPOINT = f"{self.BASE_URL}/credentials/api"
        self.OAUTH_TOKEN_ENDPOINT = f"{self.BASE_URL}/oauth2/token"
        self.DATA_UPLOAD_ENDPOINT = f"{self.BASE_URL}/data/upload"
        self.DATA_ENDPOINT = f"{self.BASE_URL}/data"

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

    def createSignedUrl(self, id, user, expectedStatus, file_type=None, params=[]):
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
