import pytest
from utils import logger


@pytest.mark.skipif(
    "gen3-user-data-library" not in pytest.deployed_services,
    reason="gen3-user-data-library service is not running on this environment",
)
class TestUserDataLibrary(object):
    def test_user_crud_data_library_records(self):
        """
        Scenario: User can CRUD data library records
        Steps:
            1. Create a data library record.
            2. Read the data library record to verify it was created in step 1.
            3. Update the data library record.
            4. Read the data library record to verify it was updated in step 3.
            5. Delete the data library record.
        """
        return

    def test_create_multiple_data_library_records_same_data(self):
        """
        Scenario: Create multiple data library records using same data and verify only record was created
        Steps:
            1. Create a data library record.
            2. Read the data library record to verify it was created in step 1.
            3. Create multiple data library record with the same data.
            4. Verify only one record is present after step 3.
            5. Delete the data library record.
        """
        return
