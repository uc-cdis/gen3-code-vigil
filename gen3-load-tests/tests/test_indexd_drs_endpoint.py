import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from utils import K6_LOAD_TESTING_SCRIPTS_PATH, SAMPLE_DESCRIPTORS_PATH
from utils import k6_load_test as k6
from utils import logger
from utils import test_setup as setup


@pytest.mark.indexd_drs_endpoint
class TestIndexdDrsEndpoint:
    def setup_method(self):
        # Initialize gen3sdk objects needed
        self.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )

        # Load the sample descriptor data
        self.sample_descriptor_file_path = (
            SAMPLE_DESCRIPTORS_PATH
            / "load-test-indexd-drs-endpoint-bottleneck-sample.json"
        )
        self.sample_descriptor_data = setup.get_sample_descriptor_data(
            self.sample_descriptor_file_path
        )

    def test_create_indexd_records(self):
        guids_list = []
        # Retrieve all indexd records
        index_records = setup.get_indexd_records(
            self.auth, indexd_record_acl="phs000178"
        )
        # If no record is present create one
        if len(index_records) == 0:
            record_data = (
                {
                    "acl": ["phs000178"],
                    "authz": ["/programs/phs000178"],
                    "file_name": "load_test_file",
                    "hashes": {"md5": "e5c9a0d417f65226f564f438120381c5"},
                    "size": 129,
                    "urls": [
                        "s3://qa-dcp-databucket-gen3/testdata",
                        "gs://qa-dcp-databucket-gen3/file.txt",
                    ],
                },
            )
            record = self.index.create_record(**record_data)
        else:
            for record in index_records:
                guids_list.append(record["did"])

        env_vars = {
            "GUIDS_LIST": ",".join(guids_list).replace("'", ""),
            "RELEASE_VERSION": "1.0.0",
            "GEN3_HOST": f"{pytest.hostname}",
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "VIRTUAL_USERS": f'{[entry for entry in self.sample_descriptor_data["virtual_users"]]}'.replace(
                "'", '"'
            ),
            "SIGNED_URL_PROTOCOL": "s3",
        }

        # Run k6 load test
        js_script_path = (
            K6_LOAD_TESTING_SCRIPTS_PATH
            / f"{self.sample_descriptor_data['service']}-{self.sample_descriptor_data['load_test_scenario']}.js"
        )
        result = k6.run_k6_load_test(env_vars, js_script_path)
        k6.get_k6_results(result.stdout)
