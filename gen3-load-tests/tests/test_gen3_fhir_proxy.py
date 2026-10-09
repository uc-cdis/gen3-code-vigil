import os

import pytest
from gen3.auth import Gen3Auth
from utils import load_test

# DEFAULT_VU = '[{"duration": "10s", "target": 10}, {"duration": "30s", "target": 50}, {"duration": "30s", "target": 50}, {"duration": "10s", "target": 0}]'
DEFAULT_VU = '[{"duration": "10s", "target": 2}, {"duration": "30s", "target": 10}, {"duration": "30s", "target": 10}, {"duration": "10s", "target": 0}]'


@pytest.mark.gen3_fhir_proxy_load
class TestGen3FhirProxyLoad:
    def setup_method(self):
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
            "BASE_PATH": "/fhir",
            "VIRTUAL_USERS": os.getenv("VIRTUAL_USERS", DEFAULT_VU),
        }

        # Run k6 load test via code-vigil's shared utility
        result = load_test.run_load_test(env_vars)

        # Process and assert results
        load_test.get_results(
            result, env_vars["SERVICE"], env_vars["LOAD_TEST_SCENARIO"]
        )
