import os
import pytest
import requests

from cdislogging import get_logger
from gen3.auth import Gen3Auth
import time

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Guppy(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}"
        self.API_GUPPY_ENDPOINT = "/guppy"

    def validate_guppy_status(self, user):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        url = self.API_AUDIT_ENDPOINT + "/_status"
        response = auth.curl(path=url)
        logger.info("Guppy status code : " + str(response.status_code))
        assert expectedStatus == response.status_code
        return True
