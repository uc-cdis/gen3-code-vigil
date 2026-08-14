import json
import os

import pandas as pd
import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from services.embedding import Embedding
from utils import TEST_DATA_PATH_OBJECT, load_test


@pytest.mark.gen3_embeddings
class TestGen3EmbeddingSearchUnKnownCollection:
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
        for collection_name, embedding_size in [
            ("expr_search", 256),
            ("hist_search", 1536),
        ]:
            # Generate Embedding data (~/test_data/embedding/{collection_name}.tsv)
            cls.gen3_embedding.generate_embedding_data(
                collection_name=collection_name,
                number_of_records=100,
                embedding_size=embedding_size,
            )

    def perform_load_test(self, top_k, distance_metric, append_file_name):
        expr_input_file = TEST_DATA_PATH_OBJECT / "embedding" / "expr_search.tsv"
        hist_input_file = TEST_DATA_PATH_OBJECT / "embedding" / "hist_search.tsv"
        df_expr = pd.read_csv(expr_input_file, sep="\t")
        df_hist = pd.read_csv(hist_input_file, sep="\t")
        embedding_list = (
            df_expr["embedding"][:15].tolist() + df_hist["embedding"][:15].tolist()
        )
        # Setup env_vars to pass into load runner
        env_vars = {
            "SERVICE": "embedding",
            "LOAD_TEST_SCENARIO": "search-embedding",
            "EMBEDDING_LIST": json.dumps(embedding_list),
            "APPEND_FILE_NAME": append_file_name,
            "TOP_K": str(top_k),
            "DISTANCE_METRIC": distance_metric,
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "GEN3_HOST": f"{pytest.hostname}",
            "RELEASE_VERSION": os.getenv("RELEASE_VERSION"),
            "VIRTUAL_USERS": '[{"duration": "120s", "target": 1}]',
        }

        # # Run k6 load test
        result = load_test.run_load_test(env_vars)

        # Process the results
        load_test.get_results(
            result,
            service=env_vars["SERVICE"],
            load_test_scenario=env_vars["LOAD_TEST_SCENARIO"],
            append_file_name=env_vars["APPEND_FILE_NAME"],
        )

    @pytest.mark.parametrize(
        "top_k,distance_metric",
        [
            (5, "cosine_similarity"),
            (5, "l1_distance"),
            (5, "inner_product"),
            (10, "cosine_similarity"),
            (10, "l1_distance"),
            (10, "inner_product"),
        ],
    )
    def test_embedding_search_embedding_unknown_collection(
        self, top_k, distance_metric
    ):
        self.perform_load_test(
            top_k,
            distance_metric,
            append_file_name=f"unknown-collection[{top_k}-{distance_metric}]".replace(
                "_", "-"
            ),
        )
