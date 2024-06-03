"""
CENTRALIZED AUTH
"""

import os
import pytest

from cdislogging import get_logger
from uuid import uuid4
from services.indexd import Indexd

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
        "filename": "testdata",
        "link": "s3://cdis-presigned-url-test/testdata",
        "md5": "73d643ec3f4beb9020eef0beed440ad0",
        "authz": ["/abc/programs/foo/projects/bar"],
        "size": 9,
    },
    "gen3_test_test_ile": {
        "filename": "testdata",
        "link": "s3://cdis-presigned-url-test/testdata",
        "md5": "73d643ec3f4beb9020eef0beed440ad1",
        "authz": ["/gen3/programs/test_program/projects/test_project"],
        "size": 10,
    },
    "two_projects_file": {
        "filename": "testdata",
        "link": "s3://cdis-presigned-url-test/testdata",
        "md5": "73d643ec3f4beb9020eef0beed440ad2",
        "authz": [
            "/abc/programs/test_program/projects/test_project1",
            "/abc/programs/test_program2/projects/test_project3",
        ],
        "size": 11,
    },
    "gen3_hmb_research_file": {
        "filename": "testdata",
        "link": "s3://cdis-presigned-url-test/testdata",
        "md5": "73d643ec3f4beb9020eef0beed440af1",
        "authz": [
            "/gen3/programs/test_program/projects/test_project1",
            "/consents/HMB",
        ],
        "size": 43,
    },
    "abc_hmb_research_file": {
        "filename": "testdata",
        "link": "s3://cdis-presigned-url-test/testdata",
        "md5": "73d643ec3f4beb90213ef0beed440af1",
        "authz": [
            "/abc/programs/test_program/projects/test_project1",
            "/consents/HMB",
        ],
        "size": 44,
    },
    "gru_research_file": {
        "filename": "testdata",
        "link": "s3://cdis-presigned-url-test/testdata",
        "md5": "73d655ec3f4beb9020eef0beed440af1",
        "authz": [
            "/gen3/programs/test_program/projects/test_project1",
            "/consents/GRU",
        ],
        "size": 45,
    },
    "open_access_file": {
        "filename": "testdata",
        "link": "s3://cdis-presigned-url-test/testdata",
        "md5": "73d643ec3f4beb90212ef0beed440af1",
        "authz": [
            "/open",
        ],
        "size": 46,
    },
}

new_gen3_records = {
    "foo_bar_file": {
        "filename": "testdata",
        "link": "s3://cdis-presigned-url-test/testdata",
        "md5": "73d643ec3f4beb9020eef0beed440ad4",
        "authz": ["/gen3/programs/test_program/projects/test_project"],
        "size": 9,
    },
    "delete_me": {
        "filename": "testdata",
        "link": "s3://cdis-presigned-url-test/testdata",
        "md5": "73d643ec3f4beb9020eef0beed440ac0",
        "authz": ["/gen3/programs/test_program/projects/test_project"],
        "size": 12,
    },
}

new_abc_records = {
    "foo_bar_file": {
        "filename": "testdata",
        "link": "s3://cdis-presigned-url-test/testdata",
        "md5": "73d643ec3f4beb9020eef0beed440ad5",
        "authz": ["/abc/programs/foo"],
        "size": 9,
    },
    "delete_me": {
        "filename": "testdata",
        "link": "s3://cdis-presigned-url-test/testdata",
        "md5": "73d643ec3f4beb9020eef0beed440ac1",
        "authz": ["/abc/programs/foo/projects/bar"],
        "size": 12,
    },
}


@pytest.mark.indexd
@pytest.mark.fence
class TestCentralizedAuth:
    indexd = Indexd()
    indexd_records = []

    @classmethod
    def setup_class(cls):
        gen3_foo_bar_file_guid = str(uuid4())
        gen3_delete_me = str(uuid4())
        abc_foo_bar_file_guid = str(uuid4())
        abc_delete_me = str(uuid4())

        new_gen3_records["foo_bar_file"]["did"] = gen3_foo_bar_file_guid
        new_gen3_records["delete_me"]["did"] = gen3_delete_me
        new_abc_records["foo_bar_file"]["did"] = abc_foo_bar_file_guid
        new_abc_records["delete_me"]["did"] = abc_delete_me

    def setup_method(self):
        # Removing test indexd records if they exist
        self.indexd.delete_file_indices(records=indexed_files)
        self.indexd.delete_file_indices(records=new_gen3_records)
        self.indexd.delete_file_indices(records=new_abc_records)

        # Adding indexd files used to test signed urls
        self.indexd_records = self.indexd.create_files(indexed_files)

    def teardown_method(self):
        logger.info("Deleting Indexd Records")
        for record in self.indexd_records:
            logger.info(record)
            rev = self.indexd.get_rev(record)
            self.indexd.delete_record(guid=record["did"], rev=rev)
        self.indexd_records = []

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
            8. Expect did to be missing in response from step 7, since dcf-user2 account cannot perform update.
            9. Delete the indexd record using dcf-user2 account.
            10. Expect "The record WAS deleted from indexd!" wasn't returned in step 9 since dcf-user2 account cannot perform delete.
            11. Delete the indexd records using indexing account for cleanup.
        """
        gen3_create_success = self.indexd.create_files(
            files=new_gen3_records, user="user2_account"
        )
        abc_create_success = self.indexd.create_files(
            files=new_abc_records, user="user2_account"
        )

        logger.info(gen3_create_success)
        logger.info(abc_create_success)

    '''def test_user_with_access_can_crud_indexd_records_in_namespace(cls):
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
        return

    def test_client_with_user_token_can_crud_indexd_records_in_namespace(cls):
        """
        Scenario: User with access can CRUD indexd records in namespace, not outside namespace
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
        return

    def test_client_with_user_token_create_signed_url_records_in_namespace(cls):
        """
        Scenario: Client (with access) with user token (with access) can create signed urls for records in namespace, not outside namespace
        Steps:
            1. Get user token with client main account. (Login using fence/authorize endpoint and get token)
            2. Create signed urls for file under both /abc and /gen3 projects. (Indexd records created as part of setup)
            3. File contents should only be accessible for file for /abc project since main account has access.
        """
        return

    def test_client_with_access_with_user_token_in_namespace(cls):
        """
        Scenario: Client (with access) with user token (WITHOUT access) in namespace
        Steps:
            1. Get user token with client main account. (Login using fence/authorize endpoint and get token)
            2. Create signed url for file under /gen3 project. (Indexd records created as part of setup)
            3. File contents should not be accessible for /gen3 project
        """
        return

    def test_client_without_access_with_user_token_in_namespace(cls):
        """
        Scenario: Client (WITHOUT access) with user token (with access) in namespace
        Steps:
            1. Get user token with dcf-user0 account and abc client. (Login using fence/authorize endpoint and get token)
            2. Create signed url for file under /gen3 project. (Indexd records created as part of setup)
            3. File contents should not be accessible for /gen3 project.
        """
        return

    def test_user_with_access_can_create_sgined_urls_records_namespace(cls):
        """
        Scenario: User with access can create signed urls for records in namespace, not outside namespace
        Steps:
            1. Create signed url for file under both /abc and /gen3 projects using main account. (Indexd records created as part of setup)
            2. File contents should only be accessible for file for /abc project since main account has access.
        """
        return

    def test_userinfo_endpoint_contains_authorization_information(cls):
        """
        Scenario: Test that userinfo endpoint contains authorization information (resources)
        Steps:
            1. Get user token with client main account. (Login using fence/authorize endpoint and get token)
            2. Ensure user has authorization information (resources) in the response
        """
        return

    def test_client_token_without_permission_cannot_create_signed_url(cls):
        """
        Scenario: Client with user token WITHOUT permission CANNOT create signed URL for record with authz AND logic
        Steps:
            1. Get user token with auxAcct1 account and abc client. (Login using fence/authorize endpoint and get token)
            2. Create signed url for file under /abc project using twoProjectsFile in Indexd Files. (Indexd records created as part of setup)
            3. File contents should not be accessible for file for /abc project.
        """
        return

    def test_client_token_with_permission_cannot_create_signed_url(cls):
        """
        Scenario: Client with user token WITH permission CAN create signed URL for record with authz AND logic
        Steps:
            1. Get user token with main account and abc client. (Login using fence/authorize endpoint and get token)
            2. Create signed url for file under /abc project using twoProjectsFile in Indexd Files. (Indexd records created as part of setup)
            3. File contents should be accessible for file for /abc project.
        """
        return

    def test_open_access_data_authenticated_user(cls):
        """
        Scenario: Test open access data with authenticated user
        Steps:
            1. Create signed url with dcf-user0 account for openAccessFile in Indexd files. (Indexd records created as part of setup)
            2. File contents should be accessible.
        """
        return

    def test_open_access_data_anonymous_user(cls):
        """
        Scenario: Test open access data with anonymous user
        Steps:
            1. Create signed url with anonymous account for openAccessFile in Indexd files. (Indexd records created as part of setup)
            2. File contents should be accessible.
        """
        return'''
