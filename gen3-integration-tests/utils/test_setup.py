import json
import os
import pytest
import re

from utils import logger
from pathlib import Path
from utils import TEST_DATA_PATH_OBJECT, gen3_admin_tasks

from gen3.auth import Gen3Auth


def get_api_key_and_auth_header(user):
    file_path = Path.home() / ".gen3" / f"{pytest.namespace}_{user}.json"
    try:
        api_key_json = json.loads(file_path.read_text())
    except FileNotFoundError:
        logger.error(f"API key file not found: '{file_path}'")
        raise
    try:
        auth = Gen3Auth(refresh_token=api_key_json, endpoint=f"{pytest.root_url}/user")
        access_token = auth.get_access_token()
    except Exception:
        logger.error(f"Failed to get access token using API Key: {file_path}")
        raise
    auth_header = {
        "Accept": "application/json",
        "Authorization": f"bearer {access_token}",
        "Content-Type": "application/json",
    }
    return (api_key_json, auth_header)


def get_configuration_files():
    """
    Get configuration files from the admin VM and save them at `test_data/configuration`
    """
    logger.info("Creating configuration files")
    configs = gen3_admin_tasks.get_admin_vm_configurations(pytest.namespace)
    path = TEST_DATA_PATH_OBJECT / "configuration"
    path.mkdir(parents=True, exist_ok=True)
    for file_name, contents in configs.items():
        with (path / file_name).open("w", encoding="utf-8") as f:
            f.write(contents)


def get_fence_client_info():
    # Create the client and return the client information
    data = gen3_admin_tasks.create_fence_client(test_env_namespace=pytest.namespace)
    path = TEST_DATA_PATH_OBJECT / "fence_clients"
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / "clients_creds.txt"
    with open(file_path, "w") as outfile:
        outfile.write(data)


def get_client_id_secret():
    """Gets the fence client information from TEST_DATA_PATH_OBJECT/fence_client folder"""
    path = TEST_DATA_PATH_OBJECT / "fence_clients" / "clients_creds.txt"
    with open(path, "r") as file:
        content = file.read()

    client_entries = re.findall(
        r"CLIENT_NAME:\s*([\w-]+).*?client id, client secret:\s*\(\s*\'([^\']+)\',\s*\'([^\']+)\'\s*\)",
        content,
        re.DOTALL,
    )
    # Adding the client_name, client_id and client_secret to the pytest.clients dict in conftest.py
    for name, client_id, client_secret in client_entries:
        pytest.clients[name] = {"client_id": client_id, "client_secret": client_secret}

    # if client_name in clients_dict:
    #     return clients_dict[client_name]['client_id'], clients_dict[client_name]['client_secret']
    # else:
    #     raise ValueError(f"Client Creds not found for client {client_name}")


def delete_all_fence_clients():
    gen3_admin_tasks.delete_fence_client(pytest.namespace)
