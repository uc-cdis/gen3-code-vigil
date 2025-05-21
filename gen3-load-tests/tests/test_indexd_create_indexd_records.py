import os

import pytest
from gen3.auth import Gen3Auth
from utils import load_test


@pytest.mark.indexd_create_indexd_records
class TestIndexdCreateRecords:
    def setup_method(self):
        # Initialize gen3sdk objects needed
        self.auth = Gen3Auth(
            refresh_token=pytest.api_keys["indexing_account"], endpoint=pytest.root_url
        )

    def test_create_indexd_records(self):
        env_vars = {
            "SERVICE": "indexd",
            "LOAD_TEST_SCENARIO": "create-indexd-records",
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "RELEASE_VERSION": os.getenv("RELEASE_VERSION"),
            "GEN3_HOST": f"{pytest.hostname}",
            "API_KEY": pytest.api_keys["indexing_account"]["api_key"],
            "VIRTUAL_USERS": '[{"duration": "1s", "target": 1}, {"duration": "5s", "target": 5}, {"duration": "300s", "target": 10}, {"duration": "600s", "target": 20}]',
        }

        # Run k6 load test
        result = load_test.run_load_test(env_vars)

        # Process the results
        load_test.get_results(
            result, env_vars["SERVICE"], env_vars["LOAD_TEST_SCENARIO"]
        )
