import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from gen3.submission import Gen3Submission
from utils import load_test, logger
from utils import test_setup as setup


@pytest.mark.fence_presigned_url
class TestFencePresignedURL:
    def setup_method(self):
        # Initialize gen3sdk objects needed
        self.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )
        self.index_auth = Gen3Auth(
            refresh_token=pytest.api_keys["indexing_account"], endpoint=pytest.root_url
        )
        self.index = Gen3Index(self.index_auth)

        self.guids_list = []

    def teardown_method(self):
        for did in self.guids_list:
            self.index.delete_record(guid=did)

    def test_fence_presigned_url(self):
        # Retrieve all indexd records
        index_records = setup.get_indexd_records(
            self.index_auth, indexd_record_acl="phs000178"
        )
        # If no record is present create one
        if len(index_records) == 0:
            record_data = {
                "acl": ["phs000178"],
                "authz": ["/programs/phs000178"],
                "file_name": "load_test_file",
                "hashes": {"md5": "e5c9a0d417f65226f564f438120381c5"},
                "size": 129,
                "urls": [
                    "s3://cdis-presigned-url-test/testdata",
                    "gs://cdis-presigned-url-test/testdata",
                ],
            }
            record = self.index.create_record(**record_data)
            self.guids_list.append(record["did"])
        else:
            for record in index_records:
                self.guids_list.append(record["did"])

        # Setup env_vars to pass into load runner
        env_vars = {
            "SERVICE": "fence",
            "LOAD_TEST_SCENARIO": "presigned-url",
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "GEN3_HOST": f"{pytest.hostname}",
            "GUIDS_LIST": ",".join(self.guids_list).replace("'", ""),
            "RELEASE_VERSION": "1.0.0",
            "VIRTUAL_USERS": '[{"duration": "5s", "target": 1}, {"duration": "10s", "target": 10}, {"duration": "120s", "target": 100}, {"duration": "120s", "target": 300}, {"duration": "30s", "target": 1}]',
        }

        # Run k6 load test
        result = load_test.run_load_test(env_vars)

        # Process the results
        load_test.get_results(
            result, env_vars["SERVICE"], env_vars["LOAD_TEST_SCENARIO"]
        )
