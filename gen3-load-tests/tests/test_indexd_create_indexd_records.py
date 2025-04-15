import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from utils import K6_LOAD_TESTING_SCRIPTS_PATH, SAMPLE_DESCRIPTORS_PATH
from utils import k6_load_test as k6
from utils import logger
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
        js_script_path = (
            K6_LOAD_TESTING_SCRIPTS_PATH
            / f"{self.sample_descriptor_data['service']}-{self.sample_descriptor_data['load_test_scenario']}.js"
        )
        result = k6.run_k6_load_test(env_vars, js_script_path)
        k6.get_k6_results(result.stdout)
