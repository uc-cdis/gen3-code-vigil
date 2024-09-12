import json
import os
import pytest
import subprocess
import re

from utils import logger
from pathlib import Path
from utils import TEST_DATA_PATH_OBJECT, gen3_admin_tasks

from gen3.auth import Gen3Auth


def get_kube_namespace(hostname: str = ""):
    """
    Compute the kubernetes namespace
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        return hostname.split(".")[0]
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        cmd = (
            "kubectl get configmap manifest-global -o json | jq -r '.data.environment'"
        )
        result = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
        return result.stdout.decode("utf-8")


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
        pytest.clients[client_name] = {
            "client_id": client_id,
            "client_secret": client_secret,
        }


def delete_all_fence_clients():
    gen3_admin_tasks.delete_fence_client(pytest.namespace)


def get_fence_rotated_client_info():
    # Create the client and return the client information
    data = gen3_admin_tasks.fence_client_rotate(test_env_namespace=pytest.namespace)
    path = TEST_DATA_PATH_OBJECT / "fence_clients"
    path.mkdir(parents=True, exist_ok=True)
    file_path = path / "client_rotate_creds.txt"
    with open(file_path, "w") as outfile:
        outfile.write(data)


def get_rotated_client_id_secret():
    path = TEST_DATA_PATH_OBJECT / "fence_clients" / "client_rotate_creds.txt"
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
        pytest.rotated_clients[client_name] = {
            "client_id": client_id,
            "client_secret": client_secret,
        }
