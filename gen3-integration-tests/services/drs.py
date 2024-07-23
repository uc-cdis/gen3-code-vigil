import pytest
import requests

from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from uuid import uuid4
from utils import logger


class Drs(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}"
        self.DRS_ENDPOINT = "/ga4gh/drs/v1/objects"

    def get_drs_object(self, file: dict, user="main_account"):
        """Get Drs object"""
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        try:
            id = file.get("did") or file.get("id")
        except Exception:
            id = None
        response = auth.curl(path=f"{self.DRS_ENDPOINT}/{id}")
        return response

    def get_drs_signed_url(self, file, user="main_account"):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        try:
            id = file.get("did") or file.get("id")
        except Exception:
            id = None
        access_id = file["urls"][0][:2]
        response = auth.curl(path=f"{self.DRS_ENDPOINT}/{id}/access/{access_id}")
        return response

    def get_drs_signed_url_without_header(self, file, user="main_account"):
        try:
            id = file.get("did") or file.get("id")
        except Exception:
            id = None
        access_id = file["urls"][0][:2]
        response = requests.get(
            url=f"{self.BASE_URL}{self.DRS_ENDPOINT}/{id}/access/{access_id}"
        )
        return response
