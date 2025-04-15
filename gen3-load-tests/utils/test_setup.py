import json
from pathlib import Path

import pytest
import requests
from utils import logger


def get_api_key(user):
    file_path = Path.home() / ".gen3" / f"{pytest.hostname}_{user}.json"
    try:
        api_key_json = json.loads(file_path.read_text())
    except FileNotFoundError:
        logger.error(f"API key file not found: '{file_path}'")
        raise
    return api_key_json


def get_sample_descriptor_data(file_path):
    with open(file_path, "r") as fp:
        json_data = json.load(fp)
    return json_data


def get_indexd_records(auth, indexd_record_acl=None):
    url = f"{pytest.root_url}/index/index"
    if indexd_record_acl:
        url += f"?acl={indexd_record_acl}"
    result = requests.get(url=url, auth=auth)
    assert (
        result.status_code == 200
    ), f"Expected status 200 but got {result.status_code}"
    return result.json()["records"]
