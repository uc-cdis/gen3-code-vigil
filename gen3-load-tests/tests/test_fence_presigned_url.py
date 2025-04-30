import pytest
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from utils import SAMPLE_DESCRIPTORS_PATH, load_test
from utils import test_setup as setup


@pytest.mark.fence_presigned_url
class TestFencePresignedURL:
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
            SAMPLE_DESCRIPTORS_PATH / "load-test-fence-presigned-url-stress-sample.json"
        )
        self.sample_descriptor_data = setup.get_sample_descriptor_data(
            self.sample_descriptor_file_path
        )

    def test_fence_presigned_url(self):
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

        # Setup env_vars to pass into load runner
        env_vars = {
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "RELEASE_VERSION": "1.0.0",
            "GEN3_HOST": f"{pytest.hostname}",
            "VIRTUAL_USERS": f'{[entry for entry in self.sample_descriptor_data["virtual_users"]]}'.replace(
                "'", '"'
            ),
            "GUIDS_LIST": ",".join(guids_list).replace("'", ""),
        }

        # Run k6 load test
        service = self.sample_descriptor_data["service"]
        load_test_scenario = self.sample_descriptor_data["load_test_scenario"]
        result = load_test.run_load_test(env_vars, service, load_test_scenario)

        # Process the results
        load_test.get_results(result, service, load_test_scenario)
