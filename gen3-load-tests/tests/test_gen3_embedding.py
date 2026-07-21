import json
import os

import pandas as pd
import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from services.embedding import Embedding
from utils import TEST_DATA_PATH_OBJECT, load_test, logger
from utils import test_setup as setup


@pytest.mark.gen3_embedding
class TestGen3Embedding:
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
        self.collection_data = {
            "public": {
                "collection_name": "public",
                "description": "Create collection for small dimensions testing",
                "dimensions": 256,
            },
        }
        response = self.gen3_embedding.create_collection(
            data=self.collection_data["public"]
        )
        assert (
            response.status_code == 200
        ), f"Expected status to be 200 but got {response.status_code}"

    def teardown_method(self):
        for did in self.guids_list:
            self.index.delete_record(guid=did)
        response = self.gen3_embedding.delete_collection(collection_name="public")
        assert (
            response.status_code == 204
        ), f"Expected status to be 204 but got {response.status_code}"

    def test_gen3_embedding(self):
        # Prepare data for submitting to embedding service
        embedding_tsv_file = TEST_DATA_PATH_OBJECT / "embedding" / "expr.tsv"
        df = pd.read_csv(embedding_tsv_file, sep="\t")
        split = int(len(df) * 0.8)
        embeddings_to_submit = df[:split]
        embeddins_to_search = df[split:]
        for embedding, authz, file_id, model, case_id in zip(
            embeddings_to_submit["embedding"],
            embeddings_to_submit["authz"],
            embeddings_to_submit["file_id"],
            embeddings_to_submit["model"],
            embeddings_to_submit["case_id"],
        ):
            embedding = json.loads(embedding)
            # Create embedding data
            embedding_data = {
                "embeddings": [
                    {
                        "embedding": embedding,
                        "metadata": {
                            "file_id": file_id,
                            "model": model,
                            "case_id": case_id,
                        },
                    }
                ]
            }
            response = self.gen3_embedding.create_embedding(
                collection_name="public", data=embedding_data
            )
            assert (
                response.status_code == 200
            ), f"Expected status to be 200 but got {response.status_code}"
            # Create indexd records
            self_value = response.json()["embeddings"][0]["info"]["self"]
            url_prefix = f"{pytest.root_url}/ai"
            indexd_data = {
                "file_name": file_id,
                "urls": [f"{url_prefix}{self_value}"],
                "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
                "authz": [authz],
                "size": 0,
            }

            record = self.index.create_record(**indexd_data)
            self.guids_list.append(record["did"])

        # Setup env_vars to pass into load runner
        search_embeddings = []
        for embedding in embeddins_to_search["embedding"]:
            embedding = json.loads(embedding)
            search_embeddings.append(embedding)
        env_vars = {
            "SERVICE": "embedding",
            "LOAD_TEST_SCENARIO": "search-embeddings",
            "SEARCH_EMBEDDING_LIST": json.dumps(search_embeddings),
            "COLLECTIONS_NAME": "public",
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "GEN3_HOST": f"{pytest.hostname}",
            "RELEASE_VERSION": os.getenv("RELEASE_VERSION"),
            "VIRTUAL_USERS": '[{"duration": "5s", "target": 1}, {"duration": "10s", "target": 10}, {"duration": "120s", "target": 100}, {"duration": "120s", "target": 300}, {"duration": "30s", "target": 1}]',
        }

        # Run k6 load test
        result = load_test.run_load_test(env_vars)

        # Process the results
        load_test.get_results(
            result, env_vars["SERVICE"], env_vars["LOAD_TEST_SCENARIO"]
        )
