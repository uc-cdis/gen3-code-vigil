import os
import uuid

import pytest
from gen3.auth import Gen3Auth
from utils import load_test


@pytest.mark.skip(reason="Need to implement logic for json creation")
# @pytest.mark.metadata_filter_large_database
class TestMetadataFilterLargeDatabase:
    def setup_method(self):
        # Initialize gen3sdk objects needed
        self.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )

    def test_metadata_create_and_query(self):
        # Setup env_vars to pass into k6 load runner
        env_vars = {
            "SERVICE": "metadata-service",
            "LOAD_TEST_SCENARIO": "filter-large-database",
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "NUM_OF_JSONS": "5",
            "API_KEY": pytest.api_keys["main_account"]["api_key"],
            "RELEASE_VERSION": os.getenv("RELEASE_VERSION"),
            "GEN3_HOST": f"{pytest.hostname}",
            "VIRTUAL_USERS": '[{"duration": "5s", "target": 1}]',  # , {"duration": "60s", "target": 10}, {"duration": "30s", "target": 100}]',
            "GUID1": str(uuid.uuid4()),
        }

        # Run k6 load test
        result = load_test.run_load_test(env_vars)

        # Process the results
        load_test.get_results(
            result, env_vars["SERVICE"], env_vars["LOAD_TEST_SCENARIO"]
        )
