import base64
import os

import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from utils import GEN_LOAD_TESTING_PATH, load_test


# @pytest.mark.skip(reason="Need to check on the mtls cert and key")
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

        # Guid list used for deletion in teardown_method
        self.guid_list = []

        # Get CRT and KEY from secrets
        mtls_crt = os.environ.get("MTLS_CRT")
        decoded_cert = base64.b64decode(mtls_crt)
        with open("mtls.crt", "wb") as cert_file:
            cert_file.write(decoded_cert)

        mtls_key = os.environ.get("MTLS_KEY")
        decoded_key = base64.b64decode(mtls_key)
        with open("mtls.key", "wb") as key_file:
            key_file.write(decoded_key)

    def teardown_method(self):
        for did in self.guid_list:
            self.index.delete_record(guid=did)

        if os.path.exists("./mtls.crt"):
            os.remove("./mtls.crt")

        if os.path.exists("./mtls.key"):
            os.remove("./mtls.key")

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
            "SERVICE": "ga4gh",
            "LOAD_TEST_SCENARIO": "drs-performance",
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
            "MTLS_CERT": GEN_LOAD_TESTING_PATH / "mtls.crt",
            "MTLS_KEY": GEN_LOAD_TESTING_PATH / "mtls.key",
        }

        # Run k6 load test
        result = load_test.run_load_test(env_vars)

        # Process the results
        load_test.get_results(
            result, env_vars["SERVICE"], env_vars["LOAD_TEST_SCENARIO"]
        )
