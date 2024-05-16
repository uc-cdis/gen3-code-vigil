"""
CENTRALIZED AUTH
"""
import os
import pytest

from cdislogging import get_logger

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


@pytest.mark.indexd
@pytest.mark.fence
class TestCentralizedAuth:
    def test_users_without_policies_cannot_crud(cls):
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
        return

    def test_user_with_access_can_crud_indexd_records_in_namespace(cls):
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
        return
