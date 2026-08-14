import json
import os

import pandas as pd
import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from services.embedding import Embedding
from utils import TEST_DATA_PATH_OBJECT, load_test


@pytest.mark.gen3_embeddings
class TestGen3EmbeddingSearchKnownCollection:
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
        cls.gen3_embedding = Embedding()
        for collection_name, embedding_size in [("hist_search", 1536)]:
            # Generate Embedding data (~/test_data/embedding/{collection_name}.tsv)
            cls.gen3_embedding.generate_embedding_data(
                collection_name=collection_name,
                number_of_records=100,
                embedding_size=embedding_size,
            )

    def perform_load_test(
        self, collection_name, top_k, distance_metric, append_file_name
    ):
        input_file = TEST_DATA_PATH_OBJECT / "embedding" / f"{collection_name}.tsv"
        df = pd.read_csv(input_file, sep="\t")
        embedding_list = df["embedding"][:25].tolist()
        # Setup env_vars to pass into load runner
        env_vars = {
            "SERVICE": "embedding",
            "LOAD_TEST_SCENARIO": "search-embedding",
            "EMBEDDING_LIST": json.dumps(embedding_list),
            "APPEND_FILE_NAME": append_file_name,
            "COLLECTION_NAME": collection_name,
            "TOP_K": str(top_k),
            "DISTANCE_METRIC": distance_metric,
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "GEN3_HOST": f"{pytest.hostname}",
            "RELEASE_VERSION": os.getenv("RELEASE_VERSION"),
            "VIRTUAL_USERS": '[{"duration": "120s", "target": 1}]',
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
        "collection_name,top_k,distance_metric",
        [
            ("hist_search", 5, "cosine_similarity"),
            ("hist_search", 5, "l1_distance"),
            ("hist_search", 5, "inner_product"),
            ("hist_search", 10, "cosine_similarity"),
            ("hist_search", 10, "l1_distance"),
            ("hist_search", 10, "inner_product"),
        ],
    )
    def test_embedding_search_embedding_known_collection(
        self, collection_name, top_k, distance_metric
    ):
        self.perform_load_test(
            collection_name,
            top_k,
            distance_metric,
            append_file_name=f"known-collection[{collection_name}-{top_k}-{distance_metric}]",
        )
