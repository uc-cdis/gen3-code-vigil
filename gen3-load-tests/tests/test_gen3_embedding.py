import json
import os
import subprocess
from pathlib import Path

import pandas as pd
import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from services.embedding import Embedding
from utils import TEST_DATA_PATH_OBJECT, load_test, logger
from utils import test_setup as setup


@pytest.mark.gen3_embedding
class TestGen3EmbeddingBulkContentRetrieval:
    def setup_method(self):
        # Initialize gen3sdk objects needed
        self.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )
        self.index_auth = Gen3Auth(
            refresh_token=pytest.api_keys["indexing_account"], endpoint=pytest.root_url
        )
        self.index = Gen3Index(self.index_auth)
        self.guids_list = []
        self.gen3_embedding = Embedding()

    def teardown_method(self):
        for did in self.guids_list:
            self.index.delete_record(guid=did)
        response = self.gen3_embedding.delete_collection(collection_name="test_expr")
        assert (
            response.status_code == 204
        ), f"Expected status to be 204 but got {response.status_code}"

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
        response = self.gen3_embedding.create_collection(
            data=self.collection_data[collection_name]
        )
        assert (
            response.status_code == 200
        ), f"Expected status to be 200 but got {response.status_code}"
        # Publish Data into Embeddings Collections
        embedding_tsv_file = TEST_DATA_PATH_OBJECT / "embedding" / file_name
        cmd = f"gen3 --auth {main_file_path} ai embeddings publish {embedding_tsv_file} --default-collection {collection_name} --batch-size 50"
        result = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if result.returncode != 0:
            raise Exception(result.stderr.decode("utf-8"))
        # Convert Published Embeddings Manifests into Indexing Manifests
        expr_output_tsv_file = TEST_DATA_PATH_OBJECT / "embedding" / "expr_output.tsv"
        cmd = f"gen3 --auth {main_file_path} ai embeddings convert {expr_output_tsv_file} --url-prefix {url_prefix}"
        result = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if result.returncode != 0:
            raise Exception(result.stderr.decode("utf-8"))
        expr_output_converted_file = (
            TEST_DATA_PATH_OBJECT / "embedding" / "expr_output_converted.tsv"
        )
        cmd = f'gen3 objects manifest validate-manifest-format {expr_output_converted_file} --allowed-protocols "https http"'
        result = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if result.returncode != 0:
            raise Exception(result.stderr.decode("utf-8"))
        # Create Gen3 Indexed Records with the Indexing Manifest
        expr_output_converted_indexed_file = (
            TEST_DATA_PATH_OBJECT / "embedding" / "expr_output_converted_indexed.tsv"
        )
        cmd = f"gen3 --auth {indexing_file_path} objects manifest publish {expr_output_converted_file} --out-manifest-file {expr_output_converted_indexed_file} --thread-num 1"
        result = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if result.returncode != 0:
            raise Exception(result.stderr.decode("utf-8"))

    def perform_load_test(self, append_file_name):
        expr_output_converted_indexed_file = (
            TEST_DATA_PATH_OBJECT / "embedding" / "expr_output_converted_indexed.tsv"
        )
        df = pd.read_csv(
            expr_output_converted_indexed_file, sep="\t", header=None, names=["guids"]
        )
        self.guids_list = df["guids"][:500].astype(str).tolist()
        # Setup env_vars to pass into load runner
        env_vars = {
            "SERVICE": "embedding",
            "LOAD_TEST_SCENARIO": "bulk-content-retieval",
            "APPEND_FILE_NAME": append_file_name,
            "GUIDS_LIST": json.dumps(self.guids_list),
            "COLLECTIONS_NAME": "test_expr",
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "GEN3_HOST": f"{pytest.hostname}",
            "RELEASE_VERSION": os.getenv("RELEASE_VERSION"),
            "VIRTUAL_USERS": '[{"duration": "5s", "target": 1}, {"duration": "10s", "target": 10}, {"duration": "120s", "target": 100}, {"duration": "120s", "target": 300}, {"duration": "30s", "target": 1}]',
        }

        # Run k6 load test
        result = load_test.run_load_test(env_vars)

        # Process the results
        load_test.get_results(
            result,
            service=env_vars["SERVICE"],
            load_test_scenario=env_vars["LOAD_TEST_SCENARIO"],
            append_file_name=env_vars["APPEND_FILE_NAME"],
        )

    def test_embedding_bulk_content_retieval_small(self):
        self.prepare_embeddings(
            collection_name="test_expr", dimensions=256, file_name="expr.tsv"
        )
        self.perform_load_test(append_file_name="small")
