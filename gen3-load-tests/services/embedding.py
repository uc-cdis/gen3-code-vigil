import csv
import json
import os
import random
import string
import subprocess
import time
import uuid
from pathlib import Path

import numpy as np
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

    def search_embedding(self, collection_name, data, user="main_account"):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        response = requests.post(
            url=f"{self.BASE_URL}{self.COLLECTIONS_ENDPOINT}/{collection_name}/search",
            json=data,
            auth=auth,
        )
        logger.info(f"Status code after searching embedding: {response.status_code}")
        return response

    def prepare_embeddings(self, collection_name, dimensions, file_name):
        url_prefix = f"{pytest.root_url}/ai"
        main_file_path = (
            Path.home() / ".gen3" / f"{pytest.namespace}_{"main_account"}.json"
        )
        indexing_file_path = (
            Path.home() / ".gen3" / f"{pytest.namespace}_{"indexing_account"}.json"
        )
        # Create Embeddings Collections
        self.collection_data = {
            collection_name: {
                "collection_name": collection_name,
                "description": "Create collection for small dimensions testing",
                "dimensions": dimensions,
            },
        }
        response = self.create_collection(data=self.collection_data[collection_name])
        assert (
            response.status_code == 200
        ), f"Expected status to be 200 but got {response.status_code}"
        # Publish Data into Embeddings Collections
        embedding_tsv_file = TEST_DATA_PATH_OBJECT / "embedding" / file_name
        start_time = time.perf_counter()
        cmd = f"gen3 --auth {main_file_path} ai embeddings publish {embedding_tsv_file} --default-collection {collection_name} --batch-size 1000"
        result = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        logger.info(
            f"Time Taken to publish data into embedding: {time.perf_counter() - start_time:.3f}s"
        )
        if result.returncode != 0:
            raise Exception(result.stderr.decode("utf-8"))
        # Convert Published Embeddings Manifests into Indexing Manifests
        output_tsv_file = (
            TEST_DATA_PATH_OBJECT / "embedding" / f"{collection_name}_output.tsv"
        )
        start_time = time.perf_counter()
        cmd = f"gen3 --auth {main_file_path} ai embeddings convert {output_tsv_file} --url-prefix {url_prefix}"
        result = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        logger.info(
            f"Time Taken to convert into indexing manifests: {time.perf_counter() - start_time:.3f}s"
        )
        if result.returncode != 0:
            raise Exception(result.stderr.decode("utf-8"))
        output_converted_file = (
            TEST_DATA_PATH_OBJECT
            / "embedding"
            / f"{collection_name}_output_converted.tsv"
        )
        start_time = time.perf_counter()
        cmd = f'gen3 objects manifest validate-manifest-format {output_converted_file} --allowed-protocols "https http"'
        result = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        logger.info(
            f"Time Taken to validate indexing manifests: {time.perf_counter() - start_time:.3f}s"
        )
        if result.returncode != 0:
            raise Exception(result.stderr.decode("utf-8"))
        # Create Gen3 Indexed Records with the Indexing Manifest
        output_converted_indexed_file = (
            TEST_DATA_PATH_OBJECT
            / "embedding"
            / f"{collection_name}_output_converted_indexed.tsv"
        )
        start_time = time.perf_counter()
        cmd = f"gen3 --auth {indexing_file_path} objects manifest publish {output_converted_file} --out-manifest-file {output_converted_indexed_file} --thread-num 1"
        result = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        logger.info(
            f"Time Taken to create indexd records: {time.perf_counter() - start_time:.3f}s"
        )
        if result.returncode != 0:
            raise Exception(result.stderr.decode("utf-8"))

    def set_embeddings_replica(self, replica_count):
        cmd = f"kubectl scale deployment gen3-embeddings-deployment --replicas={replica_count} -n {pytest.namespace}"
        result = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if result.returncode != 0:
            raise Exception(result.stderr.decode("utf-8"))
        cmd = f"kubectl -n {pytest.namespace} rollout status deployment/gen3-embeddings-deployment --timeout=5m"
        result = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if result.returncode != 0:
            raise Exception(result.stderr.decode("utf-8"))
        # Give additional buffer time
        time.sleep(30)

    def generate_embedding_data(
        self, collection_name, number_of_records, embedding_size, prefix="ABCD"
    ):
        path = TEST_DATA_PATH_OBJECT / "embedding"
        path.mkdir(parents=True, exist_ok=True)
        rng = np.random.default_rng(0)
        tsv_file = TEST_DATA_PATH_OBJECT / "embedding" / f"{collection_name}.tsv"
        if os.path.exists(tsv_file):
            os.remove(tsv_file)
        with open(tsv_file, "w+", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerow(
                [
                    "embedding",
                    "authz",
                    "collection_name",
                    "collection_id",
                    "case_id",
                    "file_id",
                    "model",
                ]
            )
            for i in range(number_of_records):
                embedding = rng.uniform(-1, 1, size=embedding_size).tolist()
                # Generate collection_id and case_id
                collection_id = f"{prefix}-{random.randint(0, 99):02d}-{random.randint(0, 9999):04d}"
                code = "".join(
                    random.choices(string.ascii_uppercase + string.digits, k=3)
                )
                num = f"{random.randint(0, 99):02d}"
                dx = f"DX{random.randint(0, 9)}"
                uid = uuid.uuid4()
                case_id = f"{collection_id}-{code}-{num}-{dx}.{uid}"

                # Write row to tsv file
                writer.writerow(
                    [
                        embedding,
                        "/programs/dev/projects/testproject1",
                        collection_name,
                        "",
                        collection_id,
                        case_id,
                        collection_name,
                    ]
                )
