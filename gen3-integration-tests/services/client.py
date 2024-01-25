import subprocess
import pytest
import os

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Client(object):
    def __init__(
        self, client_name, user_name, client_type, arborist_policies, expires_in
    ):
        self.client_name = client_name
        self.user_name = user_name
        self.client_type = client_type
        self.arborist_policies = arborist_policies
        self.expires_in = expires_in
        self._client = None

    @staticmethod
    def create_client(
        client_name, user_name, client_type, expires_in, arborist_policies=None
    ):
        fence_cmd = "fence-create"

        if arborist_policies and "ARBORIST_CLIENT_POLICIES" in os.environ:
            fence_cmd += f" --arborist http://arborist-service/"

        if client_type == "client_credentials":
            fence_cmd += f" client-create --client {client_name} --grant-types client_credentials"
        elif client_type == "implicit":
            fence_cmd += f" client-create --client {client_name} --user {user_name} --urls https://{pytest.root_url} --grant-types implicit --public"
        else:
            fence_cmd += f" client-create --client {client_name} --user {user_name} --urls https://{pytest.root_url}"

        if arborist_policies and "ARBORIST_CLIENT_POLICIES" in os.environ:
            fence_cmd += f" --policies {arborist_policies}"

        if expires_in:
            fence_cmd += f" --expires-in {expires_in}"

        print(f"running: {fence_cmd}")
        res_cmd = subprocess.run(
            fence_cmd, shell=True, stdout=subprocess.PIPE, text=True
        )
        # parsing the response to format: ('<client ID>', '<client secret>')
        arr = (
            res_cmd.stdout.replace("(", "").replace(")", "").replace("'", "").split(",")
        )
        arr = [val.strip() for val in arr]

        return {"client_id": arr[0], "client_secret": arr[1]}

    @staticmethod
    def delete_client(client_name):
        delete_client_cmd = f"fence-create client-delete --client {client_name}"
        delete_client = subprocess.run(
            delete_client_cmd, shell=True, stdout=subprocess.PIPE, text=True
        )
        print(f"Client deleted: {delete_client.stdout.strip()}")

    @property
    def client(self):
        if not self._client:
            self.delete_client(self.client_name)
            self._client = self.create_client(
                self.client_name,
                self.user_name,
                self.client_type,
                self.expires_in,
                self.arborist_policies,
            )
        return {**self._client}

    @property
    def id(self):
        return self.client["client_id"]

    @property
    def secret(self):
        return self.client["client_secret"]
