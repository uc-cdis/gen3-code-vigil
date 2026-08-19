import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
import requests
from gen3.auth import Gen3Auth
from gen3.tools.download.drs_download import (
    Downloadable,
    DownloadManager,
    get_download_url_using_drs,
    list_drs_object,
)
from utils import TEST_DATA_PATH_OBJECT, logger


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

    def get_drs_object_using_gen3sdk(self, file: dict, user="main_account"):
        """Get Drs object"""
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        id = file.get("did") or file.get("id")
        response = list_drs_object(
            hostname=pytest.hostname,
            auth=auth,
            object_id=id,
        )
        return response

    def get_drs_signed_url(self, file, user="main_account"):
        """Get Drs signed url"""
        auth = self._auth(user)
        id = self._extract_id(file)
        access_id = file["urls"][0][:2]
        response = auth.curl(path=f"{self.DRS_ENDPOINT}/{id}/access/{access_id}")
        return response

    def get_drs_signed_url_using_gen3sdk(self, file, access_token):
        """Get Drs signed url"""
        try:
            id = file.get("did") or file.get("id")
        except Exception:
            # id is set to None to test the negative test scenario
            id = None
        access_id = file["urls"][0][:2]
        result = get_download_url_using_drs(
            drs_hostname=pytest.hostname,
            object_id=id,
            access_method=access_id,
            access_token=access_token,
        )
        response, status_code = result
        return response, status_code

    def get_drs_download(self, file, user="main_account"):
        """Get Drs signed url"""
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        path = TEST_DATA_PATH_OBJECT / "drs_download"
        if os.path.exists(path):
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
        try:
            id = file.get("did") or file.get("id")
        except Exception:
            # id is set to None to test the negative test scenario
            id = None
        data = [Downloadable(object_id=id, hostname=pytest.hostname)]
        downloader = DownloadManager(
            hostname=pytest.hostname,
            auth=auth,
            download_list=data,
        )
        response = downloader.download(object_list=[data[0]], save_directory=path)
        logger.info(response)
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
        # response = auth.curl(path=self.DRS_ENDPOINT, request="POST", data=body)
        response = requests.post(
            url=f"{self.BASE_URL}{self.DRS_ENDPOINT}",
            data=body,
            auth=auth,
        )
        logger.info(
            f"Status code after getting bulk drs objects: {response.status_code}"
        )
        return response

    def get_bulk_signed_urls(
        self, bulk_access_ids: list, user: str = "main_account"
    ) -> requests.Response:
        """Get bulk presigned URLs (POST /objects/access)"""
        auth = self._auth(user)
        body = json.dumps({"bulk_object_access_ids": bulk_access_ids})
        # response = auth.curl(
        #     path=f"{self.DRS_ENDPOINT}/access", request="POST", data=body
        # )
        response = requests.post(
            url=f"{self.BASE_URL}{self.DRS_ENDPOINT}/access",
            data=body,
            auth=auth,
        )
        logger.info(
            f"Status code after getting bulk drs objects: {response.status_code}"
        )
        return response
