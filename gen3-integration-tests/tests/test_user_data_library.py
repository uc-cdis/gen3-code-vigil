import pytest
from pages.data_library_page import DataLibraryPage
from pages.login import LoginPage
from services.userdatalibrary import UserDataLibrary
from utils import logger
from utils.test_execution import screenshot


@pytest.fixture()
def page_setup(page):
    yield page
    page.close()


@pytest.mark.skipif(
    "gen3-user-data-library" not in pytest.deployed_services,
    reason="gen3-user-data-library service is not running on this environment",
)
@pytest.mark.gen3_user_data_library
@pytest.mark.frontend
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

    @classmethod
    def teardown_class(cls):
        # Delete the list after all tests are run.
        gen3_udl = UserDataLibrary()
        gen3_udl.delete_list(user="main_account")

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

        if not pytest.frontend_url:
            # Delete the data library list
            gen3_udl.delete_list(user="main_account", list_id=list_id)

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
        if not pytest.frontend_url:
            # Delete the data library list
            gen3_udl.delete_list(user="main_account", list_id=list_id)

    @pytest.mark.skipif(
        "frontend-framework" not in pytest.deployed_services,
        reason="Frontend-framework services are not running on this environment",
    )
    def test_data_library_page(self, page_setup):
        """
        Scenario:
            From Data Library Page export selected data items to Terra by
            selecting the entries created by the above api tests.
        Steps:
            1. Login and Navigate to Data Library and expand first row created by the above api tests
            2. Select list item entries and click Retrieve button on selected data
            3. Select all entries on dialog/modal and perform Terra export option
            4. Export data and Close export modal
            5. Delete list
        """
        # Login
        login_page = LoginPage()
        login_page.go_to(page_setup)
        login_page.login(page_setup)

        # Navigate to Data Library Page and Expand first row
        data_library_page = DataLibraryPage()
        data_library_page.go_to(page_setup)
        data_library_page.assert_first_row_exists(
            page_setup
        )  # Assert that data exists on data library page.

        data_library_page.expand_first_row(page_setup)
        screenshot(page_setup, "ExpandedRow")

        # Select first entry and click Retrieve button on selected data
        data_library_page.select_first_child_entry(page_setup)
        data_library_page.retrieve_selected_data(page_setup)
        screenshot(page_setup, "RetrieveSelectedData")

        # Select all entries on "Retrieve Data" dialog and select Tera
        data_library_page.select_all_entries(page_setup)
        data_library_page.select_export_to_terra(page_setup)
        screenshot(page_setup, "TerraExportSelected")

        # Do the Export and close dialog window
        data_library_page.export_data(page_setup)
        data_library_page.close_modal(page_setup)
        screenshot(page_setup, "RetrieveDataModalClosed")

        # Delete list
        data_library_page.delete_list(page_setup)
        screenshot(page_setup, "ListDeleted")

    @pytest.mark.skipif(
        True,
        reason="# KNOWN DEFECT - https://ctds-planx.atlassian.net/browse/PD-61",
    )
    def test_list_created_by_main_user_not_accessible_by_another_user(self):
        """
        Scenario: Create multiple data library lists using same data and verify only list was created
        Steps:
            1. Create a data library list for user main_account
            2. Read the data library list to verify it was created in step 1.
            3. Read the data library list using user indexing_account.
            4. Validate indexing_account user is not able to access list created by user main_account
        """
        gen3_udl = UserDataLibrary()

        # Create the data library list
        data_library_list = gen3_udl.create_list(
            user="main_account", data=self.test_data_create
        )
        for key in data_library_list["lists"].keys():
            list_id = key

        # Retrieve the list
        logger.info("Reading list by main_account user")
        main_account_list = gen3_udl.read_list(user="main_account", list_id=list_id)
        logger.info(main_account_list)

        # Retrieve the list
        logger.info("Reading list by indexing_account user")
        indexing_account_list = gen3_udl.read_list(
            user="indexing_account", list_id=list_id
        )
        assert (
            indexing_account_list == "list_id not found!"
        ), f"Expected no list but got {indexing_account_list}"

        # Delete the data library list
        gen3_udl.delete_list(user="main_account", list_id=list_id)
