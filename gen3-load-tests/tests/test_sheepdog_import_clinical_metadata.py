import pytest
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission
from utils import load_test
from utils import test_setup as setup


@pytest.mark.sheepdog_import_clinical_metadata
class TestSheepdogImportClinicalMetadata:
    def setup_method(self):
        # Initialize gen3sdk objects needed
        self.auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )

        setup.create_program(self.auth, "DEV")
        setup.create_project(self.auth, "DEV", "test")

        self.submission = Gen3Submission(auth_provider=self.auth)
        data = {
            "type": "study",
            "submitter_id": "study_9ad93324ff",
            "study_registration": "",
            "study_id": "study_9ad93324ff",
            "projects": {"code": "test"},
        }
        self.submission.submit_record("DEV", "test", data)

    def test_sheepdog_import_clinical_metadata(self):
        env_vars = {
            "SERVICE": "sheepdog",
            "LOAD_TEST_SCENARIO": "import-clinical-metadata",
            "ACCESS_TOKEN": self.auth.get_access_token(),
            "RELEASE_VERSION": "1.0.0",
            "GEN3_HOST": f"{pytest.hostname}",
            "VIRTUAL_USERS": '[{"duration": "1s", "target": 1}, {"duration": "5s", "target": 5}, {"duration": "300s", "target": 10}]',
        }

        # Run k6 load test
        result = load_test.run_load_test(env_vars)

        # Process the results
        load_test.get_results(
            result, env_vars["SERVICE"], env_vars["LOAD_TEST_SCENARIO"]
        )
