import pytest
from services.userdatalibrary import UserDataLibrary
from utils.misc import retry


@pytest.mark.skipif(
    "gen3-user-data-library" not in pytest.deployed_services,
    reason="gen3-user-data-library service is not running on this environment",
)
@pytest.mark.gen3_user_data_library
class TestUserDataLibrary(object):
    def setup_class(cls):
        cls.test_data_create = {
            "lists": [
                {
                    "name": "My Saved List asdf4",
                    "items": {
                        "drs://dg.4503:943200c3-271d-4a04-a2b6-040272239a64": {
                            "dataset_guid": "phs000001.v1.p1.THIS_IS_DIFFERENT",
                            "type": "GA4GH_DRS",
                        }
                    },
                }
            ]
        }

        cls.test_data_update = {
            "name": "My Saved List asdf4",
            "items": {
                "drs://dg.4503:THIS_IS_NEW": {
                    "dataset_guid": "phs000002.v1.p1.c1",
                    "type": "GA4GH_DRS",
                },
                "drs://dg.4503:943200c3-271d-4a04-a2b6-040272239a64": {
                    "dataset_guid": "phs000001.v1.p1.THIS_IS_DIFFERENT",
                    "type": "GA4GH_DRS",
                },
            },
        }

    def teardown_method(self):
        # Delete the list after each test
        gen3_udl = UserDataLibrary()
        gen3_udl.delete_list(user="main_account")

    # TODO: Remove retry after PPS-2020 is fixed
    @retry(times=3, delay=10, exceptions=(AssertionError))
    def test_user_crud_data_library_lists(self):
        """
        Scenario: User can CRUD data library lists
        Steps:
            1. Create a data library list.
            2. Read the data library list to verify it was created in step 1.
            3. Update the data library list.
            4. Read the data library list to verify it was updated in step 3.
            5. Delete the data library list.
        """
        gen3_udl = UserDataLibrary()

        # Create the data library list
        data_library_list = gen3_udl.create_list(
            user="main_account", data=self.test_data_create
        )
        for key in data_library_list["lists"].keys():
            list_id = key

        # Retrieve the list
        gen3_udl.read_list(user="main_account", list_id=list_id)

        # Update the data library list
        gen3_udl.update_list(
            user="main_account", data=self.test_data_update, list_id=list_id
        )

        # Delete the data library list
        gen3_udl.delete_list(user="main_account", list_id=list_id)

    # TODO: Remove retry after PPS-2020 is fixed
    @retry(times=3, delay=10, exceptions=(AssertionError))
    def test_create_multiple_data_library_lists_same_data(self):
        """
        Scenario: Create multiple data library lists using same data and verify only list was created
        Steps:
            1. Create a data library list.
            2. Read the data library list to verify it was created in step 1.
            3. Create multiple data library list with the same data.
            4. Expect 409 status when creating new records
            5. Delete the data library list.
        """
        gen3_udl = UserDataLibrary()

        # Create the data library list
        data_library_list = gen3_udl.create_list(
            user="main_account", data=self.test_data_create
        )
        for key in data_library_list["lists"].keys():
            list_id = key

        # Retrieve the list
        gen3_udl.read_list(user="main_account", list_id=list_id)

        gen3_udl.create_list(
            user="main_account", data=self.test_data_create, expected_status=409
        )

        # Delete the data library list
        gen3_udl.delete_list(user="main_account", list_id=list_id)
