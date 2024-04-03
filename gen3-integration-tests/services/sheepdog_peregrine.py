import os
import pytest
import requests

from cdislogging import get_logger
from gen3.auth import Gen3Auth
from utils import TEST_DATA_PATH_OBJECT
from utils import nodes
import requests


logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class SheepdogPeregrine(object):
    def __init__(self):
        self.BASE_ADD_ENDPOINT = "/api/v0/submission"

    def addNode(self, node, user):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        response = requests.put(
            url=pytest.root_url + self.BASE_ADD_ENDPOINT, data=node, auth=auth
        )
        # response = auth.curl(path=url, request='PUT', data=node)
        logger.info(response)
