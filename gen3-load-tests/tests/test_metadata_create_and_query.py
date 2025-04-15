import base64
import uuid

import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from utils import K6_LOAD_TESTING_SCRIPTS_PATH, SAMPLE_DESCRIPTORS_PATH
from utils import k6_load_test as k6
from utils import logger
from utils import test_setup as setup


@pytest.mark.skip(reason="This is not working, need to check")
@pytest.mark.metadata_create_and_query
class TestMetadataCreateAndQuery:
    def setup_method(self):
        # Initialize gen3sdk objects needed
        self.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )

        # Load the sample descriptor data
        self.sample_descriptor_file_path = (
            SAMPLE_DESCRIPTORS_PATH
            / "load-test-metadata-service-create-and-query-sample.json"
        )
        self.sample_descriptor_data = setup.get_sample_descriptor_data(
            self.sample_descriptor_file_path
        )

    def test_metadata_create_and_query(self):
        if "username" in self.sample_descriptor_data["basic_auth"]:
            username = self.sample_descriptor_data["basic_auth"]["username"]
            password = self.sample_descriptor_data["basic_auth"]["password"]
            auth_string = f"{username}:{password}"
            basic_auth = base64.b64encode(auth_string.encode()).decode()
        else:
            basic_auth = ""
        # Setup env_vars to pass into k6 load runner
        env_vars = {
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "BASIC_AUTH": basic_auth,
            "MDS_TEST_DATA": str(self.sample_descriptor_data["mds_test_data"]),
            "RELEASE_VERSION": "1.0.0",
            "GEN3_HOST": f"{pytest.hostname}",
            "VIRTUAL_USERS": f'{[entry for entry in self.sample_descriptor_data["virtual_users"]]}'.replace(
                "'", '"'
            ),
            "GUID1": str(uuid.uuid4()),
            "GUID2": str(uuid.uuid4()),
        }

        # Run k6 load test
        js_script_path = (
            K6_LOAD_TESTING_SCRIPTS_PATH
            / f"{self.sample_descriptor_data['service']}-{self.sample_descriptor_data['load_test_scenario']}.js"
        )
        result = k6.run_k6_load_test(env_vars, js_script_path)
        logger.info(result.stdout)
        logger.info(result.stderr)
        k6.get_k6_results(result.stdout)
