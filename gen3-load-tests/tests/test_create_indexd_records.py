import pytest
from gen3.auth import Gen3Auth
from utils import K6_LOAD_TESTING_SCRIPTS_PATH, logger
from utils import test_setup as setup


@pytest.mark.create_indexd_records
class TestCreateIndexdRecords:
    def test_create_indexd_records(self):
        # auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url)
        env_vars = {
            "RELEASE_VERSION": "1.0.0",
            "GEN3_HOST": f"{pytest.hostname}",
            "API_KEY": str(pytest.api_keys["main_account"]),
            "VIRTUAL_USERS": '[{ "duration": "1s", "target": 1 }, { "duration": "10s", "target": 10 }, { "duration": "300s", "target": 100 }, { "duration": "30s", "target": 1 }]',
        }
        script_path = K6_LOAD_TESTING_SCRIPTS_PATH / "create-indexd-records.js"
        result = setup.run_k6_load_test(env_vars, script_path)
        logger.info(result.stdout)
        logger.info(result.stderr)
