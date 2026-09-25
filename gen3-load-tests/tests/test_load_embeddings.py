import csv
import json
import os
import random
import string
import subprocess
import time
import uuid
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from services.embedding import Embedding
from utils import TEST_DATA_PATH_OBJECT, load_test, logger
from utils import test_setup as setup


@pytest.mark.gen3_embeddings
# @pytest.mark.skip(reason="Run only when needed")
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
        cls.collection_name = "hist_tcga_search"
        cls.embedding_size = 2560
        cls.records_per_chunk = 3000000
        cls.batch_size = 10000

    # def test_load_data(self):
    #     prefix = "ABCD"
    #     # Generate Embedding data (~/test_data/embedding/{collection_name}.tsv)
    #     path = TEST_DATA_PATH_OBJECT / "embedding"
    #     path.mkdir(parents=True, exist_ok=True)
    #     run_num = int(os.getenv("RUN_NUM"))
    #     attempt_num = int(os.getenv("ATTEMPT_NUM"))
    #     seed = np.random.SeedSequence([attempt_num, run_num])
    #     rng = np.random.default_rng(seed)

    #     start_record = 0
    #     end_record = self.records_per_chunk
    #     for batch_start in range(start_record, end_record, self.batch_size):
    #         tsv_file = (
    #             TEST_DATA_PATH_OBJECT / "embedding" / f"{self.collection_name}.tsv"
    #         )
    #         batch_end = min(batch_start + self.batch_size, end_record)
    #         logger.info(f"Generating records {batch_start:,} - {batch_end - 1:,}")
    #         if os.path.exists(tsv_file):
    #             os.remove(tsv_file)
    #         with open(tsv_file, "w+", newline="", encoding="utf-8") as f:
    #             writer = csv.writer(f, delimiter="\t")
    #             writer.writerow(
    #                 [
    #                     "embedding",
    #                     "authz",
    #                     "collection_name",
    #                     "collection_id",
    #                     "case_id",
    #                     "file_id",
    #                     "model",
    #                 ]
    #             )
    #             for record_id in range(batch_start, batch_end):
    #                 embedding = rng.uniform(-1, 1, size=self.embedding_size).tolist()
    #                 # Generate case_id and file_id
    #                 case_id = f"{prefix}-{random.randint(0, 99):02d}-{random.randint(0, 9999):04d}"
    #                 code = "".join(
    #                     random.choices(string.ascii_uppercase + string.digits, k=3)
    #                 )
    #                 num = f"{random.randint(0, 99):02d}"
    #                 dx = f"DX{random.randint(0, 9)}"
    #                 uid = uuid.uuid4()
    #                 file_id = f"{case_id}-{code}-{num}-{dx}.{uid}"

    #                 # Write row to tsv file
    #                 writer.writerow(
    #                     [
    #                         embedding,
    #                         "/programs/dev/projects/testproject1",
    #                         self.collection_name,
    #                         "",
    #                         case_id,
    #                         file_id,
    #                         self.collection_name,
    #                     ]
    #                 )
    #         try:
    #             self.gen3_embedding.publish_embeddings(
    #                 collection_name=self.collection_name,
    #                 file_name=f"{self.collection_name}.tsv",
    #                 number_of_records=self.batch_size,
    #             )
    #         except Exception as e:
    #             logger.info(e)

    def test_load_embeddings(self):
        path = TEST_DATA_PATH_OBJECT / "embedding"
        h5_files = [f for f in path.iterdir() if f.is_file() and f.suffix == ".h5"]
        manifest = pd.read_csv(path / "manifest.csv")
        slide_to_case = dict(zip(manifest["slide"], manifest["case"]))
        tsv_file = TEST_DATA_PATH_OBJECT / "embedding" / f"{self.collection_name}.tsv"
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
                    "loc",
                ]
            )
            for h5_file in h5_files:
                slide_name = h5_file.stem
                case_id = slide_to_case.get(slide_name)
                if case_id is None:
                    logger.warning(f"No case found for slide: {slide_name}, skipping")
                    continue
                logger.info(f"Case id: {case_id}")
                with h5py.File(h5_file, "r") as hf:
                    features = hf["features"][:]
                    locs = hf["loc"][:]
                logger.info(f"Loaded {len(features)} embeddings from {h5_file.name}")
                code = "".join(
                    random.choices(string.ascii_uppercase + string.digits, k=3)
                )
                num = f"{random.randint(0, 99):02d}"
                dx = f"DX{random.randint(0, 9)}"
                uid = uuid.uuid4()
                file_id = f"{case_id}-{code}-{num}-{dx}.{uid}"
                for embedding, loc in zip(features, locs):
                    writer.writerow(
                        [
                            embedding.tolist(),
                            "/programs/dev/projects/testproject1",
                            self.collection_name,
                            "",
                            case_id,
                            file_id,
                            self.collection_name,
                            loc.tolist(),
                        ]
                    )
