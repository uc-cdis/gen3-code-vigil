import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from utils import K6_LOAD_TESTING_SCRIPTS_PATH, SAMPLE_DESCRIPTORS_PATH, logger
from utils import test_setup as setup


@pytest.mark.fence_presigned_url
class TestFencePresignedURL:
    def setup_method(self):
        # Initialize gen3sdk objects needed
        self.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )
        self.index = Gen3Index(self.auth)

        # Load the sample descriptor data
        self.sample_descriptor_file_path = (
            SAMPLE_DESCRIPTORS_PATH / "load-test-fence-presigned-url-stress-sample.json"
        )
        self.sample_descriptor_data = setup.get_sample_descriptor_data(
            self.sample_descriptor_file_path
        )

    def test_fence_presigned_url(self):
        guids_list = []
        # Retrieve all indexd records
        index_records = self.index.get_all_records()
        for record in index_records:
            guids_list.append(record["did"])

        # Setup env_vars to pass into k6 load runner
        env_vars = {
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "RELEASE_VERSION": "1.0.0",
            "GEN3_HOST": f"{pytest.hostname}",
            "VIRTUAL_USERS": '[{ "duration": "1s", "target": 1 }, { "duration": "10s", "target": 10 }, { "duration": "300s", "target": 100 }, { "duration": "30s", "target": 1 }]',
            "GUIDS_LIST": str(guids_list).replace(" ", "").replace("'", ""),
        }

        # Run k6 load test
        js_script_path = (
            K6_LOAD_TESTING_SCRIPTS_PATH
            / f"{self.sample_descriptor_data['service']}-{self.sample_descriptor_data['load_test_scenario']}.js"
        )
        result = setup.run_k6_load_test(env_vars, js_script_path)
        setup.get_k6_results(result.stdout)
