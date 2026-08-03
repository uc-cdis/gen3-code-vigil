import json
import os
import subprocess
import time
from pathlib import Path

import pandas as pd
import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from services.embedding import Embedding
from utils import TEST_DATA_PATH_OBJECT, load_test, logger
from utils import test_setup as setup


@pytest.mark.gen3_embedding
class TestGen3EmbeddingBulkRetrievalSmall:
    @classmethod
    def setup_class(cls):
        # Initialize gen3sdk objects needed
        cls.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )
        cls.index_auth = Gen3Auth(
            refresh_token=pytest.api_keys["indexing_account"], endpoint=pytest.root_url
        )
        cls.index = Gen3Index(cls.index_auth)
        cls.guids_list = []
        cls.gen3_embedding = Embedding()

        cls.gen3_embedding.generate_embedding_data(
            collection_name="expr", number_of_records=10000, embedding_size=256
        )

        cls.gen3_embedding.prepare_embeddings(
            collection_name="expr",
            dimensions=256,
            file_name="expr.tsv",
            number_of_records=10000,
        )

    @classmethod
    def teardown_class(cls):
        for did in cls.guids_list:
            cls.index.delete_record(guid=did)
        response = cls.gen3_embedding.delete_collection(collection_name="expr")
        assert (
            response.status_code == 204
        ), f"Expected status to be 204 but got {response.status_code}"

    def perform_load_test(self, collection_name, append_file_name, bulk_content):
        output_converted_indexed_file = (
            TEST_DATA_PATH_OBJECT
            / "embedding"
            / f"{collection_name}_output_converted_indexed.tsv"
        )
        df = pd.read_csv(output_converted_indexed_file, sep="\t")
        logger.info(f"Dimensions for indexd_df: {df.shape}")
        self.guids_list = df["guid"][:bulk_content].astype(str).tolist()
        # Setup env_vars to pass into load runner
        env_vars = {
            "SERVICE": "embedding",
            "LOAD_TEST_SCENARIO": "bulk-content-retieval",
            "APPEND_FILE_NAME": append_file_name,
            "GUIDS_LIST": json.dumps(self.guids_list),
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "GEN3_HOST": f"{pytest.hostname}",
            "RELEASE_VERSION": os.getenv("RELEASE_VERSION"),
            "VIRTUAL_USERS": '[{"duration": "30s", "target": 1}]',
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

    @pytest.mark.parametrize(
        "replica_count,bulk_content",
        [
            (1, 500),
            (1, 1000),
            (1, 2000),
            (2, 500),
            (2, 1000),
            (2, 2000),
            (3, 500),
            (3, 1000),
            (3, 2000),
        ],
    )
    def test_embedding_bulk_content_retieval_small(self, replica_count, bulk_content):
        self.gen3_embedding.set_embeddings_replica(replica_count=replica_count)
        self.perform_load_test(
            collection_name="expr",
            append_file_name=f"small[{replica_count}-{bulk_content}]",
            bulk_content=bulk_content,
        )
