import json

import pytest
import requests
from gen3.auth import Gen3Auth
from utils import TEST_DATA_PATH_OBJECT, logger
from utils.misc import retry


class Embedding(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/ai/vectorstore"
        self.COLLECTIONS_ENDPOINT = "/collections"
        self.EMBEDDINGS_ENDPOINT = "/embeddings"

    def create_collection(self, data, user="main_account"):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        response = requests.post(
            url=f"{self.BASE_URL}{self.COLLECTIONS_ENDPOINT}",
            json=data,
            auth=auth,
        )
        logger.info(f"Status code after creating collection: {response.status_code}")
        return response

    def get_collection(self, collection_name, user="main_account"):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        response = auth.curl(path=f"{self.COLLECTIONS_ENDPOINT}/{collection_name}")
        logger.info(f"Status code after getting collection: {response.status_code}")
        return response.json()

    def update_collection(self, collection_name, data, user="main_account"):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        response = requests.patch(
            url=f"{self.BASE_URL}{self.COLLECTIONS_ENDPOINT}/{collection_name}",
            json=data,
            auth=auth,
        )
        logger.info(f"Status code after updating collection: {response.status_code}")
        return response

    def delete_collection(self, collection_name, user="main_account"):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        response = requests.delete(
            url=f"{self.BASE_URL}{self.COLLECTIONS_ENDPOINT}/{collection_name}",
            auth=auth,
        )
        logger.info(f"Status code after deleting collection: {response.status_code}")
        return response

    def create_embedding(self, collection_name, data, user="main_account"):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        response = requests.post(
            url=f"{self.BASE_URL}{self.COLLECTIONS_ENDPOINT}/{collection_name}{self.EMBEDDINGS_ENDPOINT}",
            json=data,
            auth=auth,
        )
        logger.info(response.content)
        logger.info(f"Status code after creating embedding: {response.status_code}")
        return response

    def get_embedding(self, collection_name, user="main_account"):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        response = auth.curl(
            path=f"{self.COLLECTIONS_ENDPOINT}/{collection_name}{self.EMBEDDINGS_ENDPOINT}"
        )
        logger.info(f"Status code after getting embedding: {response.status_code}")
        return response.json()

    def update_embedding(self, collection_name, data, user="main_account"):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        response = requests.put(
            url=f"{self.BASE_URL}{self.COLLECTIONS_ENDPOINT}/{collection_name}{self.EMBEDDINGS_ENDPOINT}",
            json=data,
            auth=auth,
        )
        logger.info(f"Status code after updating embedding: {response.status_code}")
        return response

    def delete_embedding(self, collection_name, embedding_id, user="main_account"):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        response = requests.delete(
            url=f"{self.BASE_URL}{self.COLLECTIONS_ENDPOINT}/{collection_name}{self.EMBEDDINGS_ENDPOINT}/{embedding_id}",
            auth=auth,
        )
        logger.info(f"Status code after deleting embedding: {response.status_code}")
        return response
