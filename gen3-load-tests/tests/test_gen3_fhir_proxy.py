import os

import pytest
from gen3.auth import Gen3Auth
from utils import load_test


@pytest.mark.gen3_fhir_proxy_load
class TestGen3FhirProxyLoad:
    def setup_method(self):
        # Initialize Gen3 SDK authentication against the target environment
        self.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )

    def test_gen3_fhir_proxy_patient_search(self):
        env_vars = {
            "SERVICE": "gen3-fhir-proxy",
            "LOAD_TEST_SCENARIO": "patient-search",
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "RELEASE_VERSION": os.getenv("RELEASE_VERSION", "latest"),
            "GEN3_HOST": f"{pytest.hostname}",
            "VIRTUAL_USERS": '[{"duration": "10s", "target": 5}, {"duration": "60s", "target": 10}, {"duration": "10s", "target": 0}]',
        }

        # Run k6 load test via code-vigil's shared utility
        result = load_test.run_load_test(env_vars)

        # Process and assert results
        load_test.get_results(
            result, env_vars["SERVICE"], env_vars["LOAD_TEST_SCENARIO"]
        )
