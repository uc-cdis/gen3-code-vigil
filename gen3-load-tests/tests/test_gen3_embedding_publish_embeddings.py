import json
import os
import subprocess
import time
from pathlib import Path
from statistics import mean

import pytest
from gen3.auth import Gen3Auth
from services.embedding import Embedding
from utils import LOAD_TESTING_OUTPUT_PATH, TEST_DATA_PATH_OBJECT, load_test, logger
from utils import test_setup as setup
from utils.test_execution import attach_json_file


@pytest.mark.gen3_embeddings
class TestGen3EmbeddingPublishEmbeddings:
    @classmethod
    def setup_class(cls):
        # Initialize gen3sdk objects needed
        cls.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )
        cls.gen3_embedding = Embedding()

    def percentile(self, values, p):
        if not values:
            return 0

        values = sorted(values)
        index = int(len(values) * (p / 100))

        # prevent out-of-range index
        index = min(index, len(values) - 1)

        return values[index]

    def publish_embeddings(self, collection_name, number_of_records, dimensions):
        # Generate the embeddings and store in tsv file
        self.gen3_embedding.generate_embedding_data(
            collection_name=collection_name,
            number_of_records=number_of_records,
            embedding_size=dimensions,
        )
        # Delete collection
        response = self.gen3_embedding.delete_collection(
            collection_name=collection_name
        )
        assert (
            response.status_code == 204
        ), f"Expected status to be 204 but got {response.status_code}"
        iterations = 10
        durations = []
        passes = 0
        fails = 0
        test_start = time.perf_counter()
        for i in range(iterations):
            response = self.gen3_embedding.create_collection(
                collection_name, dimensions
            )
            file_name = f"{collection_name}.tsv"
            start = time.perf_counter()
            try:
                # Run the publish command
                duration_ms, result = self.gen3_embedding.publish_embeddings(
                    collection_name, file_name, number_of_records
                )
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
            finally:
                response = self.gen3_embedding.delete_collection(
                    collection_name=collection_name
                )
                assert (
                    response.status_code == 204
                ), f"Expected status to be 204 but got {response.status_code}"

        test_duration_seconds = time.perf_counter() - test_start
        summary = {
            "metrics": {
                "checks": {
                    "passes": passes,
                    "fails": fails,
                    "value": (
                        round(passes / (passes + fails), 4) if (passes + fails) else 0
                    ),
                    "rate": (
                        round((passes / iterations) * 100, 2) if (passes + fails) else 0
                    ),
                },
                "iterations": {
                    "count": iterations,
                    "rate": round(iterations / test_duration_seconds, 2),
                },
                "http_req_duration": {
                    "min": round(min(durations), 2),
                    "avg": round(mean(durations), 2),
                    "med": round(self.percentile(durations, 50), 2),
                    "max": round(max(durations), 2),
                    "p(90)": round(self.percentile(durations, 90), 2),
                    "p(95)": round(self.percentile(durations, 95), 2),
                },
                "data_sent": {"count": 0, "rate": 0},
            }
        }

        file_name = f"embedding-publish-embedding-gen3sdk[{collection_name}-{number_of_records}-{dimensions}].json"
        output_path = LOAD_TESTING_OUTPUT_PATH / file_name
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)

        load_test.get_results(
            result,
            service="embedding",
            load_test_scenario="publish-embedding",
            append_file_name=f"gen3sdk[{collection_name}-{number_of_records}-{dimensions}]",
        )

    @pytest.mark.parametrize(
        "collection_name,number_of_records,dimensions",
        [
            ("expr", 50000, 256),
            ("hist", 50000, 1536),
        ],
    )
    def test_embedding_publish_embedding_gen3sdk(
        self, collection_name, number_of_records, dimensions
    ):
        self.publish_embeddings(collection_name, number_of_records, dimensions)
