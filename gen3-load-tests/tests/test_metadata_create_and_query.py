import os
import uuid

import pytest
from gen3.auth import Gen3Auth
from utils import load_test


 @pytest.mark.skip(reason="This is not working, need to check")
#@pytest.mark.metadata_create_and_query
class TestMetadataCreateAndQuery:
    def setup_method(self):
        # Initialize gen3sdk objects needed
        self.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )

    def test_metadata_create_and_query(self):
        # Setup env_vars to pass into k6 load runner
        env_vars = {
            "SERVICE": "metadata-service",
            "LOAD_TEST_SCENARIO": "create-and-query",
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "BASIC_AUTH": "",
            "MDS_TEST_DATA": '{"filter1": "a=1", "filter2": "nestedData.b=2", "fictitiousRecord1": {"a": 1}, "fictitiousRecord2": {"nestedData": {"b": 2}},}',
            "RELEASE_VERSION": os.getenv("RELEASE_VERSION"),
            "GEN3_HOST": f"{pytest.hostname}",
            "VIRTUAL_USERS": '[{"duration": "1s", "target": 1}, {"duration": "10s", "target": 10}, {"duration": "300s", "target": 100}, {"duration": "30s", "target": 1}]',
            "GUID1": str(uuid.uuid4()),
            "GUID2": str(uuid.uuid4()),
        }

        # Run k6 load test
        result = load_test.run_load_test(env_vars)

        # Process the results
        load_test.get_results(
            result, env_vars["SERVICE"], env_vars["LOAD_TEST_SCENARIO"]
        )
