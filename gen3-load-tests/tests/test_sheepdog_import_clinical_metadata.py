import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from utils import K6_LOAD_TESTING_SCRIPTS_PATH, SAMPLE_DESCRIPTORS_PATH, logger
from utils import test_setup as setup


@pytest.mark.sheepdog_import_clinical_metadata
class TestSheepdogImportClinicalMetadata:
    def setup_method(self):
        # Initialize gen3sdk objects needed
        self.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )
        self.index = Gen3Index(self.auth)

        # Load the sample descriptor data
        self.sample_descriptor_file_path = (
            SAMPLE_DESCRIPTORS_PATH / "load-test-sheepdog-import-clinical-metadata.json"
        )
        self.sample_descriptor_data = setup.get_sample_descriptor_data(
            self.sample_descriptor_file_path
        )

    def test_sheepdog_import_clinical_metadata(self):
        auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )
        env_vars = {
            "ACCESS_TOKEN": auth.get_access_token(),
            "RELEASE_VERSION": "1.0.0",
            "GEN3_HOST": f"{pytest.hostname}",
            "VIRTUAL_USERS": '[{ "duration": "1s", "target": 1 }, { "duration": "5s", "target": 5 }, { "duration": "300s", "target": 10 }]',
        }
        js_script_path = (
            K6_LOAD_TESTING_SCRIPTS_PATH
            / f"{self.sample_descriptor_data['service']}-{self.sample_descriptor_data['load_test_scenario']}.js"
        )
        result = setup.run_k6_load_test(env_vars, js_script_path)
        logger.info(result.stdout)
        logger.info(result.stderr)
