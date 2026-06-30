import os
import re

import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from utils import load_test
from utils import test_setup as setup


@pytest.mark.fence_bulk_presigned_url
class TestFenceBulkPresignedURL:
    def setup_method(self):
        """Set up two authenticated clients"""
        self.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )
        self.index_auth = Gen3Auth(
            refresh_token=pytest.api_keys["indexing_account"], endpoint=pytest.root_url
        )
        self.index = Gen3Index(self.index_auth)
        self.created_guids = []
        self.guids_list = []

    def teardown_method(self):
        """Delete the indexd records the test created"""
        for did in self.created_guids:
            self.index.delete_record(guid=did)

    @staticmethod
    def _batch_sizes():
        raw_batch_sizes = os.getenv(
            "BULK_PRESIGNED_URL_BATCH_SIZES", "1,5,10,25,50,100"
        )
        return [
            int(size.strip()) for size in raw_batch_sizes.split(",") if size.strip()
        ]

    @staticmethod
    def _version_tuple(version):
        parts = re.findall(r"\d+", version or "")
        return tuple(int(part) for part in parts[:3])

    def _skip_if_bulk_drs_not_available(self):
        """Check service-info endpoint and skip if DRS version < 1.4"""
        resp = self.auth.curl(path="/ga4gh/drs/v1/service-info")
        if resp.status_code != 200:
            pytest.skip("DRS service-info endpoint not available")

        version = resp.json().get("type", {}).get("version", "1.2")
        if self._version_tuple(version) < (1, 4):
            pytest.skip("DRS bulk presigned URL endpoint requires DRS >= 1.4")

    def _ensure_indexd_records(self):
        """
        Ensure there are at least 5 x the largest batch size indexd records to test with.
        E.g. if the largest batch size is 100, ensure 500 indexd records to sample.
        """
        batch_sizes = self._batch_sizes()
        max_batch_size = max(batch_sizes)
        record_pool_size = int(
            os.getenv("BULK_PRESIGNED_URL_RECORD_POOL_SIZE", max_batch_size * 5)
        )

        index_records = setup.get_indexd_records(
            self.index_auth, indexd_record_acl="phs000178"
        )
        self.guids_list = [record["did"] for record in index_records]

        # create records until we have a good pool size
        while len(self.guids_list) < record_pool_size:
            record_data = {
                "acl": ["phs000178"],
                "authz": ["/programs/phs000178.c1"],
                "file_name": "bulk_presigned_url_load_test_file",
                "hashes": {
                    "md5": "e5c9a0d417f65226f564f438120381c5"  # pragma: allowlist secret
                },
                "size": 129,
                "urls": ["s3://cdis-presigned-url-test/testdata"],
            }
            record = self.index.create_record(**record_data)
            self.created_guids.append(record["did"])
            self.guids_list.append(record["did"])

    def test_fence_bulk_presigned_url(self):
        """
        Set up bulk test and run k6 script, then get results.
        """
        self._skip_if_bulk_drs_not_available()
        self._ensure_indexd_records()

        env_vars = {
            "SERVICE": "fence",
            "LOAD_TEST_SCENARIO": "bulk-presigned-url",
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "GEN3_HOST": pytest.hostname,
            "GUIDS_LIST": ",".join(self.guids_list).replace("'", ""),
            "RELEASE_VERSION": os.getenv("RELEASE_VERSION", ""),
            "BATCH_SIZES": ",".join(str(size) for size in self._batch_sizes()),
            "BULK_ACCESS_ID": os.getenv("BULK_PRESIGNED_URL_ACCESS_ID", "s3"),
            "BULK_TEST_VUS": os.getenv("BULK_PRESIGNED_URL_VUS", "20"),
            "BULK_TEST_DURATION": os.getenv("BULK_PRESIGNED_URL_DURATION", "60s"),
            "BULK_TEST_SCENARIO_GAP_SECONDS": os.getenv(
                "BULK_PRESIGNED_URL_SCENARIO_GAP_SECONDS", "5"
            ),
        }

        result = load_test.run_load_test(env_vars)

        load_test.get_results(
            result, env_vars["SERVICE"], env_vars["LOAD_TEST_SCENARIO"]
        )
