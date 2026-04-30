import json
from uuid import uuid4

import pytest
import requests
from gen3.auth import Gen3Auth
from utils import logger


class Drs(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}"
        self.DRS_ENDPOINT = "/ga4gh/drs/v1/objects"
        self.SERVICE_INFO_ENDPOINT = "/ga4gh/drs/v1/service-info"

    def _auth(self, user: str = "main_account") -> Gen3Auth:
        return Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)

    @staticmethod
    def _extract_id(file: dict) -> str | None:
        try:
            return file.get("did") or file.get("id")
        except Exception:
            return None

    def get_drs_object(self, file: dict, user="main_account"):
        """Get Drs object"""
        auth = self._auth(user)
        id = self._extract_id(file)
        response = auth.curl(path=f"{self.DRS_ENDPOINT}/{id}")
        return response

    def get_drs_signed_url(self, file, user="main_account"):
        """Get Drs signed url"""
        auth = self._auth(user)
        id = self._extract_id(file)
        access_id = file["urls"][0][:2]
        response = auth.curl(path=f"{self.DRS_ENDPOINT}/{id}/access/{access_id}")
        return response

    def get_drs_signed_url_without_header(self, file, user="main_account"):
        """Get Drs signed url without header"""
        auth = self._auth(user)
        id = self._extract_id(file)
        access_id = file["urls"][0][:2]
        response = auth.curl(
            path=f"{self.BASE_URL}{self.DRS_ENDPOINT}/{id}/access/{access_id}"
        )
        return response

    def get_service_info(self, user: str = "main_account") -> requests.Response:
        """Get DRS service info"""
        auth = self._auth(user)
        response = auth.curl(path=self.SERVICE_INFO_ENDPOINT)
        return response

    def get_drs_object_authorizations(
        self, file: dict, user: str = "main_account"
    ) -> requests.Response:
        """Get authorization info for a DRS object (OPTIONS /objects/{id})"""
        auth = self._auth(user)
        id = self._extract_id(file)
        url = f"{self.BASE_URL}{self.DRS_ENDPOINT}/{id}"
        response = requests.options(url, auth=auth)
        return response

    def get_bulk_object_authorizations(
        self, object_ids: list, user: str = "main_account"
    ) -> requests.Response:
        """Get bulk authorization info (OPTIONS /objects)"""
        auth = self._auth(user)
        url = f"{self.BASE_URL}{self.DRS_ENDPOINT}"
        response = requests.options(
            url, json={"bulk_object_ids": object_ids}, auth=auth
        )
        return response

    def get_bulk_drs_objects(
        self, object_ids: list, user: str = "main_account"
    ) -> requests.Response:
        """Get multiple DRS objects (POST /objects)"""
        auth = self._auth(user)
        body = json.dumps({"bulk_object_ids": object_ids})
        response = auth.curl(path=self.DRS_ENDPOINT, request="POST", data=body)
        return response

    def get_bulk_signed_urls(
        self, bulk_access_ids: list, user: str = "main_account"
    ) -> requests.Response:
        """Get bulk presigned URLs (POST /objects/access)"""
        auth = self._auth(user)
        body = json.dumps({"bulk_object_access_ids": bulk_access_ids})
        response = auth.curl(
            path=f"{self.DRS_ENDPOINT}/access", request="POST", data=body
        )
        return response
