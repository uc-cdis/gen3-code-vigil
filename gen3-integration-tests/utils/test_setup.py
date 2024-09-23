import json
import os
import pytest
import subprocess
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
    path = TEST_DATA_PATH_OBJECT / "configuration"
    path.mkdir(parents=True, exist_ok=True)
    configs = gen3_admin_tasks.get_env_configurations(pytest.namespace)
    for file_name, contents in configs.items():
        with (path / file_name).open("w", encoding="utf-8") as f:
            f.write(contents)


def delete_all_fence_clients():
    gen3_admin_tasks.delete_fence_client(pytest.namespace)


def fence_clients_setup_info():
    # Create the client and return the client information
    clients_data, rotated_clients_data = gen3_admin_tasks.setup_fence_test_clients(
        test_env_namespace=pytest.namespace
    )
    clients_path = TEST_DATA_PATH_OBJECT / "fence_clients"
    clients_path.mkdir(parents=True, exist_ok=True)
    clients_file_path = clients_path / "clients_creds.txt"
    with open(clients_file_path, "w") as outfile:
        outfile.write(clients_data)
    rotated_clients_path = TEST_DATA_PATH_OBJECT / "fence_clients"
    rotated_clients_path.mkdir(parents=True, exist_ok=True)
    rotated_clients_file_path = rotated_clients_path / "client_rotate_creds.txt"
    with open(rotated_clients_file_path, "w") as outfile:
        outfile.write(rotated_clients_data)


def get_rotated_client_id_secret():
    path = TEST_DATA_PATH_OBJECT / "fence_clients" / "client_rotate_creds.txt"
    if not os.path.exists(path):
        logger.info("clients_creds.txt doesn't exists.")
        return
    with open(path, "r") as file:
        content = file.read()

    for entry in content.split("\n"):
        if len(entry) == 0:  # Empty line
            continue
        client_name, client_details = entry.split(":")
        client_id, client_secret = re.sub(r"[\'()]", "", client_details).split(", ")
        pytest.rotated_clients[client_name] = {
            "client_id": client_id,
            "client_secret": client_secret,
        }


def get_client_id_secret():
    """Gets the fence client information from TEST_DATA_PATH_OBJECT/fence_client folder"""
    path = TEST_DATA_PATH_OBJECT / "fence_clients" / "clients_creds.txt"
    if not os.path.exists(path):
        logger.info("client_rotate_creds.txt doesn't exists.")
        return
    with open(path, "r") as file:
        content = file.read()

    for entry in content.split("\n"):
        if len(entry) == 0:  # Empty line
            continue
        client_name, client_details = entry.split(":")
        client_id, client_secret = re.sub(r"[\'()]", "", client_details).split(", ")
        pytest.clients[client_name] = {
            "client_id": client_id,
            "client_secret": client_secret,
        }
