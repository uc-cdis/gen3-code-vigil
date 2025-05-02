import pytest
from gen3.auth import Gen3Auth
from utils import load_test
from utils import test_setup as setup


@pytest.mark.indexd_drs_endpoint
class TestIndexdDrsEndpoint:
    def setup_method(self):
        # Initialize gen3sdk objects needed
        self.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )

    def test_create_indexd_records(self):
        guids_list = []
        # Retrieve all indexd records
        index_records = setup.get_indexd_records(
            self.auth, indexd_record_acl="phs000178"
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
                    "s3://qa-dcp-databucket-gen3/testdata",
                    "gs://qa-dcp-databucket-gen3/file.txt",
                ],
            }
            record = self.index.create_record(**record_data)
        else:
            for record in index_records:
                guids_list.append(record["did"])

        env_vars = {
            "SERVICE": "indexd",
            "LOAD_TEST_SCENARIO": "drs-endpoint",
            "GUIDS_LIST": ",".join(guids_list).replace("'", ""),
            "RELEASE_VERSION": "1.0.0",
            "GEN3_HOST": f"{pytest.hostname}",
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "VIRTUAL_USERS": '[{"duration": "1s", "target": 1}, {"duration": "5s", "target": 1}, {"duration": "1s", "target": 2}, {"duration": "5s", "target": 2}, {"duration": "1s", "target": 3}, {"duration": "5s", "target": 3}, {"duration": "1s", "target": 4}, {"duration": "5s", "target": 4}, {"duration": "1s", "target": 5}, {"duration": "5s", "target": 5}, {"duration": "1s", "target": 6}, {"duration": "5s", "target": 6}, {"duration": "1s", "target": 7}, {"duration": "5s", "target": 7}, {"duration": "1s", "target": 8}, {"duration": "5s", "target": 8}, {"duration": "1s", "target": 9}, {"duration": "5s", "target": 9}, {"duration": "1s", "target": 10}, {"duration": "5s", "target": 10}, {"duration": "1s", "target": 11}, {"duration": "5s", "target": 11}, {"duration": "1s", "target": 12}, {"duration": "5s", "target": 12}, {"duration": "1s", "target": 13}, {"duration": "5s", "target": 13}, {"duration": "1s", "target": 14}, {"duration": "5s", "target": 14}, {"duration": "1s", "target": 15}, {"duration": "5s", "target": 15}, {"duration": "1s", "target": 16}, {"duration": "5s", "target": 16}, {"duration": "1s", "target": 17}, {"duration": "5s", "target": 17}, {"duration": "1s", "target": 18}, {"duration": "5s", "target": 18}, {"duration": "1s", "target": 19}, {"duration": "5s", "target": 19}, {"duration": "1s", "target": 20}, {"duration": "5s", "target": 20}]',
            "SIGNED_URL_PROTOCOL": "s3",
        }

        # Run k6 load test
        result = load_test.run_load_test(env_vars)

        # Process the results
        load_test.get_results(
            result, env_vars["SERVICE"], env_vars["LOAD_TEST_SCENARIO"]
        )
