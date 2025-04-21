import pytest
from gen3.auth import Gen3Auth
from utils import SAMPLE_DESCRIPTORS_PATH, load_test
from utils import test_setup as setup


@pytest.mark.skip(reason="This is not working, need to check")
@pytest.mark.ga4gh_drs_performance
class TestGa4ghDrsPerformance:
    def setup_method(self):
        # Initialize gen3sdk objects needed
        self.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )

        # Load the sample descriptor data
        self.sample_descriptor_file_path = (
            SAMPLE_DESCRIPTORS_PATH / "load-test-ga4gh-drs-performance-sample.json"
        )
        self.sample_descriptor_data = setup.get_sample_descriptor_data(
            self.sample_descriptor_file_path
        )

    def test_ga4gh_drs_performance(self):
        # Setup env_vars to pass into k6 load runner
        env_vars = {
            "TARGET_ENV": "",
            "AUTHZ_LIST": "/programs/DEV/projects/test1,/programs/DEV/projects/test2,/programs/DEV/projects/test3",
            "MINIMUM_RECORDS": "10000",
            "RECORD_CHUNK_SIZE": "1024",
            "RELEASE_VERSION": "1.0.0",
            "GEN3_HOST": f"{pytest.hostname}",
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "PASSPORTS_LIST": "",
            "SIGNED_URL_PROTOCOL": "s3",
            "NUM_PARALLEL_REQUESTS": "5",
            "MTLS_DOMAIN": "ctds-test-env.planx-pla.net",
            "MTLS_CERT": "",
            "MTLS_KEY": "",
        }

        # Run k6 load test
        service = self.sample_descriptor_data["service"]
        load_test_scenario = self.sample_descriptor_data["load_test_scenario"]
        result = load_test.run_load_test(env_vars, service, load_test_scenario)

        # Process the results
        load_test.get_results(result, service, load_test_scenario)
