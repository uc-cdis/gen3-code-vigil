import os
import pytest
import requests

from cdislogging import get_logger
from gen3.auth import Gen3Auth
from utils import TEST_DATA_PATH_OBJECT
from services.peregrine import Peregrine
import requests
import json


logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class DataClient(object):
    def configure_client(self, fence: object, user: str, files: object):
        creds_path = "./temp_creds.json"
        scope = ["data", "user"]
        api_key_res = fence.create_api_key(scope=scope, user=user)
