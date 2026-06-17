import os
import shutil
from pathlib import Path

import pytest
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

    def get_drs_object(self, file: dict, user="main_account"):
        """Get Drs object"""
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        try:
            id = file.get("did") or file.get("id")
        except Exception:
            # id is set to None to test the negative test scenario
            id = None
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
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        try:
            id = file.get("did") or file.get("id")
        except Exception:
            # id is set to None to test the negative test scenario
            id = None
        access_id = file["urls"][0][:2]
        response = auth.curl(path=f"{self.DRS_ENDPOINT}/{id}/access/{access_id}")
        return response

    def get_drs_signed_url_using_gen3sdk(self, file, access_token):
        """Get Drs signed url"""
        auth = Gen3Auth(access_token=access_token, endpoint=self.BASE_URL)
        access_id = file["urls"][0][:2]
        result = get_download_url_using_drs(
            drs_hostname=pytest.hostname,
            object_id=access_id,
            access_method="s3",
            access_token=auth.get_access_token(),
        )
        response, status_code = result
        logger.info(response)
        logger.info(status_code)
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
