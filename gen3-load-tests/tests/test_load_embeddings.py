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
import pandas as pd
import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from services.embedding import Embedding
from utils import TEST_DATA_PATH_OBJECT, load_test, logger
from utils import test_setup as setup


@pytest.mark.gen3_embeddings
class TestGen3EmbeddingLoadData:
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
        cls.collection_name = "expr_search"
        cls.embedding_size = 256
        cls.records_per_chunk = 10000
        cls.batch_size = 10000
        cls.chunk_id = int(os.environ["CHUNK_ID"])
        if cls.chunk_id == 0:
            # Delete collection
            response = cls.gen3_embedding.delete_collection(
                collection_name=cls.collection_name
            )
            assert (
                response.status_code == 204
            ), f"Expected status to be 204 but got {response.status_code}"
            # Create the collection
            cls.gen3_embedding.create_collection(
                collection_name=cls.collection_name, dimensions=cls.embedding_size
            )

    def test_load_data(self):
        prefix = "ABCD"
        # Generate Embedding data (~/test_data/embedding/{collection_name}.tsv)
        path = TEST_DATA_PATH_OBJECT / "embedding"
        path.mkdir(parents=True, exist_ok=True)
        seed = np.random.SeedSequence(0)
        child_seed = seed.spawn(10)[self.chunk_id]
        rng = np.random.default_rng(child_seed)

        start_record = self.chunk_id * self.records_per_chunk
        end_record = start_record + self.records_per_chunk
        for batch_start in range(start_record, end_record, self.batch_size):
            tsv_file = (
                TEST_DATA_PATH_OBJECT / "embedding" / f"{self.collection_name}.tsv"
            )
            batch_end = min(batch_start + self.batch_size, end_record)
            logger.info(f"Generating records {batch_start:,} - {batch_end - 1:,}")
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
                for record_id in range(batch_start, batch_end):
                    embedding = rng.uniform(-1, 1, size=self.embedding_size).tolist()
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
                            self.collection_name,
                            "",
                            collection_id,
                            case_id,
                            self.collection_name,
                        ]
                    )
            try:
                self.gen3_embedding.publish_embeddings(
                    collection_name=self.collection_name,
                    file_name=f"{self.collection_name}.tsv",
                    number_of_records=self.batch_size,
                )
            except Exception as e:
                logger.info(e)
