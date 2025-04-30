import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from utils import SAMPLE_DESCRIPTORS_PATH, load_test, logger
from utils import test_setup as setup


@pytest.mark.ga4gh_drs_performance
class TestGa4ghDrsPerformance:
    def setup_method(self):
        # Initialize gen3sdk objects needed
        self.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )
        index_auth = Gen3Auth(
            refresh_token=pytest.api_keys["indexing_account"], endpoint=pytest.root_url
        )
        self.index = Gen3Index(index_auth)

        # Load the sample descriptor data
        self.sample_descriptor_file_path = (
            SAMPLE_DESCRIPTORS_PATH / "load-test-ga4gh-drs-performance-sample.json"
        )
        self.sample_descriptor_data = setup.get_sample_descriptor_data(
            self.sample_descriptor_file_path
        )

        # Guid list used for deletion in teardown_method
        self.guid_list = []

    def teardown_method(self):
        for did in self.guid_list:
            logger.info(self.index.delete_record(guid=did))

    def test_ga4gh_drs_performance(self):
        for i in range(400):
            record_data_1 = {
                "acl": ["jenkins"],
                "authz": ["/programs/jnkns/projects/jenkins"],
                "file_name": "load_test_file",
                "hashes": {"md5": "e5c9a0d417f65226f564f438120381c5"},
                "size": 129,
                "urls": [
                    "s3://cdis-presigned-url-test/testdata",
                ],
            }
            record_data_2 = {
                "acl": ["jenkins2"],
                "authz": ["/programs/jnkns/projects/jenkins2"],
                "file_name": "load_test_file",
                "hashes": {"md5": "e5c9a0d417f65226f564f438120381c5"},
                "size": 129,
                "urls": [
                    "s3://cdis-presigned-url-test/testdata",
                ],
            }
            record_data_3 = {
                "acl": ["test"],
                "authz": ["/programs/QA/projects/test"],
                "file_name": "load_test_file",
                "hashes": {"md5": "e5c9a0d417f65226f564f438120381c5"},
                "size": 129,
                "urls": [
                    "s3://cdis-presigned-url-test/testdata",
                ],
            }
            record_indexd1 = self.index.create_record(**record_data_1)
            self.guid_list.append(record_indexd1["did"])
            record_indexd2 = self.index.create_record(**record_data_2)
            self.guid_list.append(record_indexd2["did"])
            record_indexd3 = self.index.create_record(**record_data_3)
            self.guid_list.append(record_indexd3["did"])

        # Setup env_vars to pass into k6 load runner
        env_vars = {
            "TARGET_ENV": pytest.hostname,
            "AUTHZ_LIST": "/programs/jnkns/projects/jenkins,/programs/jnkns/projects/jenkins2,/programs/QA/projects/test",
            "MINIMUM_RECORDS": "1000",
            "RECORD_CHUNK_SIZE": "1024",
            "RELEASE_VERSION": "1.0.0",
            "GEN3_HOST": pytest.hostname,
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "PASSPORTS_LIST": "",
            "SIGNED_URL_PROTOCOL": "s3",
            "NUM_PARALLEL_REQUESTS": "5",
            "MTLS_DOMAIN": "ctds-test-env.planx-pla.net",
            "MTLS_CERT": "/Users/krishnaa/gen3-code-vigil/gen3-load-tests/mtls.crt",
            "MTLS_KEY": "/Users/krishnaa/gen3-code-vigil/gen3-load-tests/mtls.key",
        }

        # Run k6 load test
        service = self.sample_descriptor_data["service"]
        load_test_scenario = self.sample_descriptor_data["load_test_scenario"]
        result = load_test.run_load_test(env_vars, service, load_test_scenario)

        # Process the results
        load_test.get_results(result, service, load_test_scenario)
