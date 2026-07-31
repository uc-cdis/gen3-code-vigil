import json
import os
import subprocess
import time
from pathlib import Path
from statistics import mean

import pytest
from gen3.auth import Gen3Auth
from services.embedding import Embedding
from utils import LOAD_TESTING_OUTPUT_PATH, TEST_DATA_PATH_OBJECT, logger
from utils import test_setup as setup
from utils.test_execution import attach_json_file


@pytest.mark.gen3_embedding
class TestGen3EmbeddingPublishEmbeddings:
    @classmethod
    def setup_class(cls):
        # Initialize gen3sdk objects needed
        cls.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )
        cls.gen3_embedding = Embedding()
        cls.gen3_embedding.generate_embedding_data(
            collection_name="hist", number_of_records=10000, embedding_size=1536
        )

    @classmethod
    def teardown_class(cls):
        response = cls.gen3_embedding.delete_collection(collection_name="hist")
        assert (
            response.status_code == 204
        ), f"Expected status to be 204 but got {response.status_code}"

    def percentile(self, values, p):
        if not values:
            return 0

        values = sorted(values)
        index = int(len(values) * (p / 100))

        # prevent out-of-range index
        index = min(index, len(values) - 1)

        return values[index]

    def test_publish_embeddings(self):
        iterations = 10
        durations = []
        passes = 0
        fails = 0
        test_start = time.perf_counter()
        # Run the publish command 10 times
        for i in range(iterations):
            response = self.gen3_embedding.delete_collection(collection_name="hist")
            assert (
                response.status_code == 204
            ), f"Expected status to be 204 but got {response.status_code}"
            self.collection_data = {
                "hist": {
                    "collection_name": "hist",
                    "description": "Create collection for dimensions testing",
                    "dimensions": 1536,
                },
            }
            response = self.gen3_embedding.create_collection(
                data=self.collection_data["hist"]
            )
            start = time.perf_counter()
            try:
                main_file_path = (
                    Path.home() / ".gen3" / f"{pytest.namespace}_{"main_account"}.json"
                )
                embedding_tsv_file = TEST_DATA_PATH_OBJECT / "embedding" / "hist.tsv"
                cmd = f'gen3 --auth {main_file_path} ai embeddings publish {embedding_tsv_file} --default-collection "hist" --batch-size 1000'
                result = subprocess.run(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=300,
                )
                logger.info(
                    f"Time Taken to publish data into embedding: {time.perf_counter() - start:.3f}s"
                )
                duration_ms = (time.perf_counter() - start) * 1000
                durations.append(duration_ms)

                if result.returncode == 0:
                    passes += 1
                else:
                    fails += 1
                    logger.info(f"Iteration {i + 1} failed:")
                    logger.info(result.stderr)
            except subprocess.TimeoutExpired:
                duration_ms = (time.perf_counter() - start) * 1000
                durations.append(duration_ms)
                fails += 1
                logger.info(f"Iteration {i + 1} timed out")
            except Exception as e:
                fails += 1
                logger.info(f"Iteration {i + 1} error: {e}")

        test_duration_seconds = time.perf_counter() - test_start
        summary = {
            "metrics": {
                "checks": {
                    "passes": passes,
                    "fails": fails,
                    "rate": round((passes / iterations) * 100, 2),
                },
                "iterations": {
                    "count": iterations,
                    "rate": round(iterations / test_duration_seconds, 2),
                },
                "command_duration": {
                    "avg": round(mean(durations), 2),
                    "max": round(max(durations), 2),
                    "p(90)": round(self.percentile(durations, 90), 2),
                    "p(95)": round(self.percentile(durations, 95), 2),
                },
                "data_sent": {"count": 0, "rate": 0},
            }
        }
        file_name = "publish-embeddings.json"
        output_path = LOAD_TESTING_OUTPUT_PATH / file_name
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)
        attach_json_file(file_name)

        if fails != 0:
            raise Exception(f"{fails} failures were encountered.")
