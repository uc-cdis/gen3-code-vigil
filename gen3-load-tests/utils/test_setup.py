import csv
import json
import os
import re
from pathlib import Path

import pytest
import requests
from gen3.auth import Gen3Auth
from utils import TEST_DATA_PATH_OBJECT, gen3_admin_tasks, logger


def get_configuration_files():
    """
    Get configuration files from the admin VM and save them at `test_data/configuration`
    """
    logger.info("Creating configuration files")
    path = TEST_DATA_PATH_OBJECT / "configuration"
    path.mkdir(parents=True, exist_ok=True)
    configs = gen3_admin_tasks.get_env_configurations(pytest.namespace)
    for file_name, contents in configs.items():
        with (path / file_name).open("w", encoding="utf-8") as f:
            f.write(contents)


def get_api_key(user):
    file_path = Path.home() / ".gen3" / f"{pytest.namespace}_{user}.json"
    try:
        api_key_json = json.loads(file_path.read_text())
    except FileNotFoundError:
        logger.error(f"API key file not found: '{file_path}'")
        raise
    return api_key_json


def run_usersync():
    gen3_admin_tasks.run_gen3_job(
        "usersync",
        test_env_namespace=pytest.namespace,
    )
    gen3_admin_tasks.check_job_pod(
        "usersync", "gen3job", test_env_namespace=pytest.namespace
    )


def get_users():
    user_list_path = TEST_DATA_PATH_OBJECT / "test_setup" / "users.csv"
    with open(user_list_path) as f:
        users = {row["USER_ID"]: row["EMAIL"] for row in csv.DictReader(f)}
    return users


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
