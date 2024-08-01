"""
CENTRALIZED AUTH
"""

import os
import pytest

from cdislogging import get_logger
from uuid import uuid4
from services.indexd import Indexd
from services.fence import Fence
from playwright.sync_api import Page
from utils.gen3_admin_tasks import (
    create_fence_client,
    run_gen3_job,
    delete_fence_client,
)

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))

"""
NOTES:
* CRUD: Create, Read, Update, Delete
* main account: cdis.autotest@gmail.com
* auxAcct1 account: dummy-one@planx-pla.net
* indexing account: ctds.indexing.test@gmail.com
* dcf-user0 account: dcf-integration-test-0@planx-pla.net
* dcf-user2 account: dcf-integration-test-2@gmail.com
"""

indexed_files = {
    "abc_foo_bar_file": {
        "file_name": "testdata",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "authz": ["/abc/programs/foo/projects/bar"],
        "size": 9,
    },
    "gen3_test_test_file": {
        "file_name": "testdata",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad1"},
        "authz": ["/gen3/programs/test_program/projects/test_project"],
        "size": 10,
    },
    "two_projects_file": {
        "file_name": "testdata",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad2"},
        "authz": [
            "/abc/programs/test_program/projects/test_project1",
            "/abc/programs/test_program2/projects/test_project3",
        ],
        "size": 11,
    },
    "gen3_hmb_research_file": {
        "file_name": "testdata",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440af1"},
        "authz": [
            "/gen3/programs/test_program/projects/test_project1",
            "/consents/HMB",
        ],
        "size": 43,
    },
    "abc_hmb_research_file": {
        "file_name": "testdata",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb90213ef0beed440af1"},
        "authz": [
            "/abc/programs/test_program/projects/test_project1",
            "/consents/HMB",
        ],
        "size": 44,
    },
    "gru_research_file": {
        "file_name": "testdata",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d655ec3f4beb9020eef0beed440af1"},
        "authz": [
            "/gen3/programs/test_program/projects/test_project1",
            "/consents/GRU",
        ],
        "size": 45,
    },
    "open_access_file": {
        "file_name": "testdata",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb90212ef0beed440af1"},
        "authz": [
            "/open",
        ],
        "size": 46,
    },
}

new_gen3_records = {
    "foo_bar_file": {
        "file_name": "testdata",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad4"},
        "authz": ["/gen3/programs/test_program/projects/test_project"],
        "size": 9,
    },
    "delete_me": {
        "file_name": "testdata",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ac0"},
        "authz": ["/gen3/programs/test_program/projects/test_project"],
        "size": 12,
    },
}

new_abc_records = {
    "foo_bar_file": {
        "file_name": "testdata",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad5"},
        "authz": ["/abc/programs/foo"],
        "size": 9,
    },
    "delete_me": {
        "file_name": "testdata",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ac1"},
        "authz": ["/abc/programs/foo/projects/bar"],
        "size": 12,
    },
}


@pytest.mark.indexd
@pytest.mark.fence
@pytest.mark.requires_fence_client
class TestCentralizedAuth:
    indexd = Indexd()
    fence = Fence()
    page = Page
    variables = {}
    variables["created_indexd_dids"] = []

    @classmethod
    def setup_class(cls):
        # Assign the did to new_gen3_records and new_abc_records
        new_gen3_records["foo_bar_file"]["did"] = str(uuid4())
        new_gen3_records["delete_me"]["did"] = str(uuid4())
        new_abc_records["foo_bar_file"]["did"] = str(uuid4())
        new_abc_records["delete_me"]["did"] = str(uuid4())

        # Generate Client id and secrets
        cls.basic_test_client_id, cls.basic_test_client_secret = (
            cls.fence.get_client_id_secret(client_name="basic-test-client")
        )
        cls.implicit_test_client_id, cls.implicit_test_client_secret = (
            cls.fence.get_client_id_secret(client_name="basic-test-abc-client")
        )

        # Create indexd records
        for key, val in indexed_files.items():
            indexd_record = cls.indexd.create_records(records={key: val})
            cls.variables["created_indexd_dids"].append(indexd_record[0]["did"])

    @classmethod
    def teardown_class(cls):
        # Delete indexd records created in class setup
        cls.indexd.delete_records(cls.variables["created_indexd_dids"])

    def setup_method(self):
        # Removing test indexd records if they exist
        self.indexd.delete_records(
            guids=[record["did"] for record in new_gen3_records.values()]
        )
        self.indexd.delete_records(
            guids=[record["did"] for record in new_abc_records.values()]
        )

    def teardown_method(self):
        logger.info("Deleting Indexd Records")
        self.indexd.delete_records(
            guids=[record["did"] for record in new_gen3_records.values()]
        )
        self.indexd.delete_records(
            guids=[record["did"] for record in new_abc_records.values()]
        )

    def test_users_without_policies_cannot_crud(self):
        """
        Scenario: User without policies cannot CRUD indexd records in /gen3 or /abc
        Steps:
            1. Add file indices using dcf-user2 account.
            2. Fetch indexd response data for file added above using dcf-user2 account.
            3. Response returned should 404 since the indexd record is not created.
            4. Force creation of file indices using indexing account.
            5. Fetch indexd response data for file again using dcf-user2 account.
            6. Response returned should be 200 since the indexd record is created in step 4.
            7. Update the indexd record by changing the file_name using dcf-user2 account.
            8. Update should fail in step 7, since dcf-user2 account cannot perform update.
            9. Delete the indexd record using dcf-user2 account.
            10. Expect "The record WAS deleted from indexd!" wasn't returned in step 9 since dcf-user2 account cannot perform delete.
            11. Delete the indexd records using indexing account for cleanup.
        """
        # Create indexd records using dcf-user2 account
        # Both indexd record creations should fail, as dcf-user2 doesn't have access to /gen3 or /abc project
        try:
            self.indexd.create_records(records=new_gen3_records, user="user2_account")
        except Exception as e:
            if "401" not in f"{e}":
                raise f"401 status code not returned. Exception : {e}"
        try:
            self.indexd.create_records(records=new_abc_records, user="user2_account")
        except Exception as e:
            if "401" not in f"{e}":
                raise f"401 status code not returned. Exception : {e}"

        # Create indexd records using indexing_user
        self.indexd.create_records(records=new_gen3_records)
        self.indexd.create_records(records=new_abc_records)

        # Read should be successful using user2_account
        gen3_read_success = self.indexd.get_record(
            indexd_guid=new_gen3_records["foo_bar_file"]["did"], user="user2_account"
        )
        abc_read_success = self.indexd.get_record(
            indexd_guid=new_abc_records["foo_bar_file"]["did"], user="user2_account"
        )
        assert (
            "rev" in gen3_read_success.keys()
        ), "rev keyword missing in gen3_create_success"
        assert (
            "rev" in abc_read_success.keys()
        ), "rev keyword missing in abc_create_success"

        # Update should not be successful using user2_account
        filename_change = {"file_name": "test_filename"}
        assert 401 == self.indexd.update_record_via_api(
            guid=gen3_read_success["did"],
            rev=gen3_read_success["rev"],
            data=filename_change,
            user="user2_account",
        ), "Update should not have been possible using dcf-user2 account"
        assert 401 == self.indexd.update_record_via_api(
            guid=abc_read_success["did"],
            rev=abc_read_success["rev"],
            data=filename_change,
            user="user2_account",
        ), "Update should not have been possible using dcf-user2 account"

        # Delete should not be successful using user2_account
        gen3_read_success = self.indexd.get_record(
            indexd_guid=new_gen3_records["delete_me"]["did"], user="user2_account"
        )
        abc_read_success = self.indexd.get_record(
            indexd_guid=new_abc_records["delete_me"]["did"], user="user2_account"
        )
        assert 401 == self.indexd.delete_record_via_api(
            guid=gen3_read_success["did"],
            rev=gen3_read_success["rev"],
            user="user2_account",
        ), "Delete should not have been possible using dcf-user2 account"
        assert 401 == self.indexd.delete_record_via_api(
            guid=abc_read_success["did"],
            rev=abc_read_success["rev"],
            user="user2_account",
        ), "Delete should not have been possible using dcf-user2 account"

    def test_user_with_access_can_crud_indexd_records_in_namespace(self):
        """
        Scenario: User with access can CRUD indexd records in namespace, not outside namespace
        Steps:
            1. Main account user has access to /abc project and not /gen3.
            2. Create indexd records for /abc and /gen3 projects using main account.
            3. Record is only created for /abc project and not /gen3 project.
            4. Force creation of file indices for /gen3 using indexing account.
            5. Indexd records for both projects should be accessible.
            6. Update indexd records for both projects using main account.
            7. Only /abc project indexd record should be updated and have did in response from step 6.
            8. Delete indexd records for both /abc and /gen3 project using main account.
            9. Only indexd record for /abc project should get deleted.
            10. Delete the indexd record for /gen3 using indexing account for cleanup.
        """
        # Create indexd records using main_account
        # Indexd record for abc project only is created, as main_account has access to /abc project and not /gen3.
        try:
            self.indexd.create_records(records=new_gen3_records, user="main_account")
        except Exception as e:
            if "401" not in f"{e}":
                raise f"401 status code not returned. Exception : {e}"

        self.indexd.create_records(records=new_abc_records, user="main_account")

        # Create indexd records using indexing_user
        self.indexd.create_records(records=new_gen3_records)

        # Read should be successful using main_account
        gen3_read_success = self.indexd.get_record(
            indexd_guid=new_gen3_records["foo_bar_file"]["did"], user="main_account"
        )
        abc_read_success = self.indexd.get_record(
            indexd_guid=new_abc_records["foo_bar_file"]["did"], user="main_account"
        )
        assert (
            "rev" in gen3_read_success.keys()
        ), "rev keyword missing in gen3_create_success"
        assert (
            "rev" in abc_read_success.keys()
        ), "rev keyword missing in abc_create_success"

        # Update should not be successful using main_account
        filename_change = {"file_name": "test_filename"}
        assert 401 == self.indexd.update_record_via_api(
            guid=new_gen3_records["foo_bar_file"]["did"],
            rev=gen3_read_success["rev"],
            data=filename_change,
            user="main_account",
        ), "Update should not have been possible using dcf-user2 account"
        assert 200 == self.indexd.update_record_via_api(
            guid=new_abc_records["foo_bar_file"]["did"],
            rev=abc_read_success["rev"],
            data=filename_change,
            user="main_account",
        ), "Update should not have been possible using dcf-user2 account"

        # Verify updated file had updated name
        assert (
            filename_change["file_name"]
            == self.indexd.get_record(
                indexd_guid=new_abc_records["foo_bar_file"]["did"], user="main_account"
            )["file_name"]
        )

        # Delete should not be successful using user2_account
        gen3_read_success = self.indexd.get_record(
            indexd_guid=new_gen3_records["delete_me"]["did"], user="main_account"
        )
        abc_read_success = self.indexd.get_record(
            indexd_guid=new_abc_records["delete_me"]["did"], user="main_account"
        )
        assert 401 == self.indexd.delete_record_via_api(
            guid=new_gen3_records["delete_me"]["did"],
            rev=gen3_read_success["rev"],
            user="main_account",
        ), "Delete should not have been possible using main_account"
        assert 200 == self.indexd.delete_record_via_api(
            guid=new_abc_records["delete_me"]["did"],
            rev=abc_read_success["rev"],
            user="main_account",
        ), "Delete should have been possible using main_account"

    def test_client_with_user_token_can_crud_indexd_records_in_namespace(
        self, page: Page
    ):
        """
        Scenario: Client (with access) with user token (with access) can CRUD indexd records in namespace, not outside namespace
        Steps:
            1. Get user token with client main account. (Login using fence/authorize endpoint and get token)
            2. Create indexd records for /abc and /gen3 projects using main account token.
            3. Record is only created for /abc project and not /gen3 project.
            4. Force creation of file indices for /gen3 using indexing account token.
            5. Indexd records for both projects should be accessible.
            6. Update indexd records for both projects using main account token.
            7. Only /abc project indexd record should be updated and have did in response from step 6.
            8. Delete indexd records for both /abc and /gen3 project using main account token.
            9. Only indexd record for /abc project should get deleted.
            10. Delete the indexd record for /gen3 using indexing account for cleanup.
        """
        # Generate access_token
        access_token = self.fence.get_user_tokens_with_client(
            page=page,
            client_id=self.basic_test_client_id,
            client_secret=self.basic_test_client_secret,
        ).json()["access_token"]

        # Create indexd records using main_account
        # Indexd record for abc project only is created, as main_account has access to /abc project and not /gen3.
        try:
            self.indexd.create_records(
                records=new_gen3_records, access_token=access_token
            )
        except Exception as e:
            if "401" not in e:
                logger.error(f"Expected 401 but got {e}")
                raise
        self.indexd.create_records(records=new_abc_records, access_token=access_token)

        # Create gen3 records using indexing_user
        self.indexd.create_records(records=new_gen3_records)

        # Read should be successful using user2_account
        gen3_read_success = self.indexd.get_record(
            indexd_guid=new_gen3_records["foo_bar_file"]["did"],
            access_token=access_token,
        )
        abc_read_success = self.indexd.get_record(
            indexd_guid=new_abc_records["foo_bar_file"]["did"],
            access_token=access_token,
        )
        assert (
            "rev" in gen3_read_success.keys()
        ), "rev keyword missing in gen3_create_success"
        assert (
            "rev" in abc_read_success.keys()
        ), "rev keyword missing in abc_create_success"

        # Update should not be successful for gen3 record
        filename_change = {"file_name": "test_filename"}
        gen3_update_success = self.indexd.update_record_via_api(
            guid=gen3_read_success["did"],
            rev=gen3_read_success["rev"],
            data=filename_change,
            access_token=access_token,
        )
        abc_update_success = self.indexd.update_record_via_api(
            guid=abc_read_success["did"],
            rev=abc_read_success["rev"],
            data=filename_change,
            access_token=access_token,
        )
        assert (
            gen3_update_success == 401
        ), f"gen3 record was updated. Status: {gen3_update_success}"
        assert (
            abc_update_success == 200
        ), f"abc record was not updated. Status: {abc_update_success}"

        # Verify updated file had updated name
        assert (
            filename_change["file_name"]
            == self.indexd.get_record(
                indexd_guid=new_abc_records["foo_bar_file"]["did"],
                access_token=access_token,
            )["file_name"]
        )

        # Delete should not be successful for gen3 record
        gen3_delete_success = self.indexd.delete_record_via_api(
            guid=gen3_read_success["did"],
            rev=gen3_read_success["rev"],
            access_token=access_token,
        )
        abc_delete_success = self.indexd.delete_record_via_api(
            guid=abc_read_success["did"],
            rev=abc_read_success["rev"],
            access_token=access_token,
        )
        assert (
            gen3_delete_success == 401
        ), f"gen3 record was deleted. Status: {gen3_delete_success}"
        assert (
            abc_update_success == 200
        ), f"abc record was not updated. Status: {abc_delete_success}"

    def test_client_with_user_token_create_signed_url_records_in_namespace(
        self, page: Page
    ):
        """
        Scenario: Client (with access) with user token (with access) can create signed urls for records in namespace, not outside namespace
        Steps:
            1. Get user token with client main account. (Login using fence/authorize endpoint and get token)
            2. Create signed urls for file under both /abc and /gen3 projects. (Indexd records created as part of setup)
            3. File contents should only be accessible for file for /abc project since main account has access.
        """
        # Generate access_token
        access_token = self.fence.get_user_tokens_with_client(
            page=page,
            client_id=self.basic_test_abc_client_id,
            client_secret=self.basic_test_abc_client_secret,
        ).json()["access_token"]

        # Create Signed URLs for /abc and /gen3 project using access_token
        signed_url_abc_res = self.fence.create_signed_url(
            id=indexed_files["abc_foo_bar_file"]["did"],
            user=None,
            expected_status=200,
            access_token=access_token,
        )
        signed_url_gen3_res = self.fence.create_signed_url(
            id=indexed_files["gen3_test_test_file"]["did"],
            user=None,
            expected_status=401,
            access_token=access_token,
        )

        # Verify signed url is created only for /abc project and not /gen3.
        assert (
            "url" in signed_url_abc_res.keys()
        ), "Could not find url keyword in abc signed url"
        assert (
            401 == signed_url_gen3_res.status_code
        ), "Expected 401 status when creating signed url"

        # Verify the contents of /abc signed url
        self.fence.check_file_equals(
            signed_url_abc_res, "Hi Zac!\ncdis-data-client uploaded this!\n"
        )

    def test_client_with_access_with_user_token_in_namespace(self, page: Page):
        """
        Scenario: Client (with access) with user token (WITHOUT access) in namespace
        Steps:
            1. Get user token with client main account. (Login using fence/authorize endpoint and get token)
            2. Create signed url for file under /gen3 project. (Indexd records created as part of setup)
            3. File contents should not be accessible for /gen3 project
        """
        # Generate access_token
        access_token = self.fence.get_user_tokens_with_client(
            page=page,
            client_id=self.basic_test_client_id,
            client_secret=self.basic_test_client_secret,
        ).json()["access_token"]

        # Create Signed URLs for /gen3 project using access_token
        signed_url_gen3_res = self.fence.create_signed_url(
            id=indexed_files["gen3_test_test_file"]["did"],
            user=None,
            expected_status=401,
            access_token=access_token,
        )

        assert (
            401 == signed_url_gen3_res.status_code
        ), "Expected 401 status when creating signed url"

    def test_client_without_access_with_user_token_in_namespace(self, page: Page):
        """
        Scenario: Client (WITHOUT access) with user token (with access) in namespace
        Steps:
            1. Get user token with dcf-user0 account and abc client. (Login using fence/authorize endpoint and get token)
            2. Create signed url for file under /gen3 project. (Indexd records created as part of setup)
            3. File contents should not be accessible for /gen3 project.
        """
        # Generate access_token
        access_token = self.fence.get_user_tokens_with_client(
            page=page,
            client_id=self.basic_test_abc_client_id,
            client_secret=self.basic_test_abc_client_secret,
            user="user0_account",
        ).json()["access_token"]

        # Create Signed URLs for /gen3 project using access_token
        signed_url_gen3_res = self.fence.create_signed_url(
            id=indexed_files["gen3_test_test_file"]["did"],
            user=None,
            expected_status=401,
            access_token=access_token,
        )

        assert (
            401 == signed_url_gen3_res.status_code
        ), "Expected 401 status when creating signed url"

    def test_user_with_access_can_create_sgined_urls_records_namespace(self):
        """
        Scenario: User with access can create signed urls for records in namespace, not outside namespace
        Steps:
            1. Create signed url for file under both /abc and /gen3 projects using main account. (Indexd records created as part of setup)
            2. File contents should only be accessible for file for /abc project since main account has access.
        """
        # Create Signed URLs for /abc and /gen3 project using main_account
        signed_url_abc_res = self.fence.create_signed_url(
            id=indexed_files["abc_foo_bar_file"]["did"],
            user="main_account",
            expected_status=200,
        )
        signed_url_gen3_res = self.fence.create_signed_url(
            id=indexed_files["gen3_test_test_file"]["did"],
            user="main_account",
            expected_status=401,
        )

        # Verify signed url is created only for /abc project and not /gen3.
        assert (
            "url" in signed_url_abc_res.keys()
        ), "Could not find url keyword in abc signed url"
        assert (
            401 == signed_url_gen3_res.status_code
        ), "Expected 401 status when creating signed url for /gen3 project"

        # Verify the contents of /abc signed url
        self.fence.check_file_equals(
            signed_url_abc_res, "Hi Zac!\ncdis-data-client uploaded this!\n"
        )

    def test_userinfo_endpoint_contains_authorization_information(self, page: Page):
        """
        Scenario: Test that userinfo endpoint contains authorization information (resources)
        Steps:
            1. Get user token with client main account. (Login using fence/authorize endpoint and get token)
            2. Ensure user has authorization information (resources) in the response
        """
        # Generate access_token
        access_token = self.fence.get_user_tokens_with_client(
            page=page,
            client_id=self.basic_test_client_id,
            client_secret=self.basic_test_client_secret,
        ).json()["access_token"]

        # Get resources field from Get User Info
        resources_of_user = self.fence.get_user_info(access_token=access_token)[
            "resources"
        ]
        logger.info(resources_of_user)

        assert resources_of_user != None, "Resources field is None"
        assert len(resources_of_user) != 0, "Length of resouces field is 0."

    def test_client_token_without_permission_cannot_create_signed_url(self, page: Page):
        """
        Scenario: Client with user token WITHOUT permission CANNOT create signed URL for record with authz AND logic
        Steps:
            1. Get user token with auxAcct1 account and abc client. (Login using fence/authorize endpoint and get token)
            2. Create signed url for file under /abc project using twoProjectsFile in Indexd Files. (Indexd records created as part of setup)
            3. File contents should not be accessible for file for /abc project.
        """
        # Generate access_token
        access_token = self.fence.get_user_tokens_with_client(
            page=page,
            client_id=self.basic_test_abc_client_id,
            client_secret=self.basic_test_abc_client_secret,
            user="auxAcct1_account",
        ).json()["access_token"]

        # Create Signed URL using access_token
        signed_url_res = self.fence.create_signed_url(
            id=indexed_files["two_projects_file"]["did"],
            user=None,
            expected_status=401,
            access_token=access_token,
        )

        assert (
            401 == signed_url_res.status_code
        ), "Expected 401 status when creating signed url"

    def test_client_token_with_permission_cannot_create_signed_url(self, page: Page):
        """
        Scenario: Client with user token WITH permission CAN create signed URL for record with authz AND logic
        Steps:
            1. Get user token with main account and abc client. (Login using fence/authorize endpoint and get token)
            2. Create signed url for file under /abc project using twoProjectsFile in Indexd Files. (Indexd records created as part of setup)
            3. File contents should be accessible for file for /abc project.
        """
        # Generate access_token
        access_token = self.fence.get_user_tokens_with_client(
            page=page,
            client_id=self.basic_test_abc_client_id,
            client_secret=self.basic_test_abc_client_secret,
            user="main_account",
        ).json()["access_token"]

        # Create Signed URL using access_token
        signed_url_res = self.fence.create_signed_url(
            id=indexed_files["two_projects_file"]["did"],
            user=None,
            expected_status=200,
            access_token=access_token,
        )

        # Verify the contents
        self.fence.check_file_equals(
            signed_url_res, "Hi Zac!\ncdis-data-client uploaded this!\n"
        )

    def test_open_access_data_authenticated_user(self):
        """
        Scenario: Test open access data with authenticated user
        Steps:
            1. Create signed url with dcf-user2 account for openAccessFile in Indexd files. (Indexd records created as part of setup)
            2. File contents should be accessible.
        """
        # Create Signed URLs for open access file using dcf-user2 account
        signed_url_res = self.fence.create_signed_url(
            id=indexed_files["open_access_file"]["did"],
            user="user2_account",
            expected_status=200,
        )

        # Verify signed url is created only for open access file.
        assert (
            "url" in signed_url_res.keys()
        ), "Could not find url keyword in signed url"

        # Verify the contents of open access file's signed url
        self.fence.check_file_equals(
            signed_url_res, "Hi Zac!\ncdis-data-client uploaded this!\n"
        )

    def test_open_access_data_anonymous_user(self):
        """
        Scenario: Test open access data with anonymous user
        Steps:
            1. Create signed url with anonymous account for openAccessFile in Indexd files. (Indexd records created as part of setup)
            2. File contents should be accessible.
        """
        # Create Signed URLs for open access file
        signed_url_res = self.fence.create_signed_url(
            id=indexed_files["open_access_file"]["did"], user=None, expected_status=200
        )

        # Verify signed url is created only for open access file.
        assert (
            "url" in signed_url_res.keys()
        ), "Could not find url keyword in signed url"

        # Verify the contents of open access file's signed url
        self.fence.check_file_equals(
            signed_url_res, "Hi Zac!\ncdis-data-client uploaded this!\n"
        )

    def test_create_signed_url_consent_codes_multiple_policies(self):
        # Create Signed URLs for file in authorized namespace with authorized consent code (multiple policies).
        signed_url_res = self.fence.create_signed_url(
            id=indexed_files["gen3_hmb_research_file"]["did"],
            user="user0_account",
            expected_status=200,
        )

        # Verify signed url is created only for file in authorized namespace with authorized consent code (multiple policies).
        assert (
            "url" in signed_url_res.keys()
        ), "Could not find url keyword in signed url"

        # Verify the contents of authorized namespace with authorized consent code (multiple policies) signed url.
        self.fence.check_file_equals(
            signed_url_res, "Hi Zac!\ncdis-data-client uploaded this!\n"
        )

    def test_create_signed_url_consent_codes_single_policy(self):
        # Create Signed URLs for file in authorized namespace with authorized consent code (single policy).
        signed_url_res = self.fence.create_signed_url(
            id=indexed_files["gen3_hmb_research_file"]["did"],
            user="user1_account",
            expected_status=200,
        )

        # Verify signed url is created only for file in authorized namespace with authorized consent code (single policy).
        assert (
            "url" in signed_url_res.keys()
        ), "Could not find url keyword in signed url"

        # Verify the contents of authorized namespace with authorized consent code (single policy) signed url.
        self.fence.check_file_equals(
            signed_url_res, "Hi Zac!\ncdis-data-client uploaded this!\n"
        )

    def test_cannot_create_signed_url_unauthorized_consent_codes_(self):
        # Create Signed URLs for file in authorized namespace with UNauthorized consent code.
        signed_url_res = self.fence.create_signed_url(
            id=indexed_files["abc_hmb_research_file"]["did"],
            user="main_account",
            expected_status=401,
        )

        # Verify signed url is not created for file in authorized namespace with UNauthorized consent code.
        assert (
            401 == signed_url_res.status_code
        ), "Expected 401 status when creating signed url"

    def test_create_signed_url_implied_authorized_consent_codes(self):
        # Create Signed URLs for file in authorized namespace with IMPLIED authorized consent code (based on DUO hierarchy).
        signed_url_res = self.fence.create_signed_url(
            id=indexed_files["gru_research_file"]["did"],
            user="user0_account",
            expected_status=200,
        )

        # Verify signed url is created only for file in authorized namespace with IMPLIED authorized consent code (based on DUO hierarchy).
        assert (
            "url" in signed_url_res.keys()
        ), "Could not find url keyword in signed url"

        # Verify the contents of authorized namespace with IMPLIED authorized consent code (based on DUO hierarchy) signed url.
        self.fence.check_file_equals(
            signed_url_res, "Hi Zac!\ncdis-data-client uploaded this!\n"
        )
