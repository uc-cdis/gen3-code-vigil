import pytest
from gen3.auth import Gen3Auth
from utils import SAMPLE_DESCRIPTORS_PATH, load_test
from utils import test_setup as setup


@pytest.mark.indexd_create_indexd_records
class TestIndexdCreateIndexdRecords:
    def setup_method(self):
        # Initialize gen3sdk objects needed
        self.auth = Gen3Auth(
            refresh_token=pytest.api_keys["indexing_account"], endpoint=pytest.root_url
        )

        # Load the sample descriptor data
        self.sample_descriptor_file_path = (
            SAMPLE_DESCRIPTORS_PATH / "load-test-indexd-create-indexd-records.json"
        )
        self.sample_descriptor_data = setup.get_sample_descriptor_data(
            self.sample_descriptor_file_path
        )

    def test_create_indexd_records(self):
        env_vars = {
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "RELEASE_VERSION": "1.0.0",
            "GEN3_HOST": f"{pytest.hostname}",
            "API_KEY": pytest.api_keys["indexing_account"]["api_key"],
            "VIRTUAL_USERS": f'{[entry for entry in self.sample_descriptor_data["virtual_users"]]}'.replace(
                "'", '"'
            ),
        }

        # Run k6 load test
        service = self.sample_descriptor_data["service"]
        load_test_scenario = self.sample_descriptor_data["load_test_scenario"]
        result = load_test.run_load_test(env_vars, service, load_test_scenario)

        # Process the results
        load_test.get_results(result, service, load_test_scenario)
