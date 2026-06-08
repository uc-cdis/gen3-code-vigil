from uuid import uuid4

import pytest
import requests
from gen3.auth import Gen3Auth
from gen3.tools.download.drs_download import (
    get_download_url_using_drs,
    list_drs_object,
)
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
            # id is set to None to test the negative test scenario
            id = None
        # response = auth.curl(path=f"{self.DRS_ENDPOINT}/{id}")
        response = list_drs_object(pytest.hostname, auth, id)
        logger.info(response.json())
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
        # response = auth.curl(path=f"{self.DRS_ENDPOINT}/{id}/access/{access_id}")
        response = get_download_url_using_drs(
            drs_hostname=pytest.hostname,
            object_id=access_id,
            access_method="s3",
            access_token=auth.get_access_token(),
        )
        logger.info(response)
        return response
