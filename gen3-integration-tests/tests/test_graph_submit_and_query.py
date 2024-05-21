import json
import os
import pytest
import requests

from cdislogging import get_logger
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from gen3.submission import Gen3SubmissionQueryError
from utils.gen3_admin_tasks import create_access_token
from services.indexd import Indexd
from services.graph import GraphDataTools
from pages.login import LoginPage
from pages.files_landing_page import FilesLandingPage

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def skip_consent_code_test(gdt: GraphDataTools):
    """
    Function to check if consent_codes is available in dictionary.
    Used to skip test if consent_codes in not available.
    """
    metadata = gdt.get_file_record()
    if "consent_codes" not in metadata.props.keys():
        logger.info("Running consent code tests since dictionary has them")
        return True
    logger.info("Skipping consent code tests since dictionary does not have them")
    return False


@pytest.mark.graph_submission
class TestGraphSubmitAndQuery:
    auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
    sd_tools = GraphDataTools(auth=auth, program_name="jnkns", project_code="jenkins")

    @classmethod
    def setup_class(cls):
        cls.sd_tools.create_program_and_project()
        cls.sd_tools.delete_all_records_in_test_project()

    def teardown_method(self, method):
        # Delete all test records at the end of each test
        self.sd_tools.delete_all_records_in_test_project()

    @pytest.mark.graph_query
    def test_submit_query_and_delete_records(self):
        """
        Scenario: Submit graph data and perform various queries.
        Steps:
            1. Submit graph data
            2. Check that querying the records return the submitted data
            3. Check that querying an invalid property errors
            4. Check that filtering on string properties works
            5. Check that node count queries work
            6. Delete the graph data
        """
        logger.info("Submitting test records")
        self.sd_tools.submit_all_test_records()

        logger.info(
            "For each node, query all the properties and check that the response matches"
        )
        for node_name, record in self.sd_tools.test_records.items():
            primitive_props = [
                prop for prop in record.props.keys() if type(record.props[prop]) != dict
            ]
            props_str = " ".join(primitive_props)
            query = f'query {{ {node_name} (project_id: "{self.sd_tools.project_id}") {{ {props_str} }} }}'
            received_data = (
                self.sd_tools.graphql_query(query).get("data", {}).get(node_name, [])
            )
            assert (
                len(received_data) == 1
            ), "Submitted 1 record so expected query to return 1 record"
            for prop in primitive_props:
                assert received_data[0][prop] == record.props[prop]

        # We use core_metadata_collection because we know links will not be an issue when submitting a new
        # record. We could also use a node at the bottom of the tree so it's easier to delete records in the
        # right node order, but the new record should not have any "1 to 1" links, or new linked records
        # should be submitted as well. For now this is easier.
        node_name = "core_metadata_collection"
        record = self.sd_tools.test_records[node_name]

        logger.info("Query an invalid property")
        query = f'query {{ {node_name} (project_id: "{self.sd_tools.project_id}") {{ prop_does_not_exist }} }}'
        with pytest.raises(
            Gen3SubmissionQueryError,
            match=f'Cannot query field "prop_does_not_exist" on type "{node_name}".',
        ):
            self.sd_tools.graphql_query(query)

        logger.info("Query with filter on a string property")
        string_prop = [
            prop for prop in record.props.keys() if type(record.props[prop]) == str
        ][0]
        string_prop_value = record.props[string_prop]
        query = f'query {{ {node_name} (project_id: "{self.sd_tools.project_id}", {string_prop}: "{string_prop_value}") {{ {string_prop} }} }}'
        received_data = (
            self.sd_tools.graphql_query(query).get("data", {}).get(node_name, [])
        )
        assert len(received_data) == 1
        assert received_data[0][string_prop] == string_prop_value

        logger.info("Query node count before and after submitting a new record")
        result = self.sd_tools.query_node_count(node_name)
        count = result.get("data", {}).get(f"_{node_name}_count")
        self.sd_tools.submit_new_record(node_name)
        result = self.sd_tools.query_node_count(node_name)
        assert result.get("data", {}).get(f"_{node_name}_count") == count + 1

    def test_submit_record_unauthenticated(self):
        """
        Scenario: Submit record unauthenticated
        Steps:
            1. Generate an expired token
            2. Create a record with expired token
            3. Creating record should fail
        """
        # Generate an expired token
        res = create_access_token(
            pytest.namespace, "fence", "1", "cdis.autotest@gmail.com"
        )

        res = res.splitlines()[-1].strip()
        auth_header = {
            "Accept": "application/json",
            "Authorization": f"bearer {res}",
            "Content-Type": "application/json",
        }

        # Create a record with expired token
        first_record = self.sd_tools.test_records[self.sd_tools.submission_order[0]]
        response = requests.put(
            url=pytest.root_url + "/api/v0/submission/jnkns/jenkins",
            data=json.dumps(first_record.props),
            headers=auth_header,
        )
        assert (
            response.status_code == 401
        ), f"Should have failed to create record. Response: {response}"

    @pytest.mark.graph_query
    def test_submit_record_without_parent(self):
        """
        Scenario: Submit record without parent
        Steps:
            1. Create a record using sheepdog. Verify record is present.
            2. Perform a query using an invalid project_id.
            3. Validate no records are returned for the node
        """
        # Verify parent record does not exist
        parent_record = self.sd_tools.test_records[self.sd_tools.submission_order[0]]
        parent_response = self.sd_tools.query_record_fields(parent_record)

        # Validate no records are returned for the node
        assert (
            len(parent_response["data"][parent_record.node_name]) == 0
        ), "Expected no records for {}. Response: {}".format(
            parent_record.node_name, parent_response
        )

        # Attempt to add second record which has a dependency on another record
        second_record = self.sd_tools.get_record_with_parent()
        # Validate submit_record fails with status code as 400
        with pytest.raises(
            requests.exceptions.HTTPError,
            match="400",
        ):
            self.sd_tools.submit_record(record=second_record)

    @pytest.mark.graph_query
    def test_filter_by_invalid_project_id(self):
        """
        Scenario: Filter by invalid project_id
        Steps:
            1. Create a record using sheepdog. Verify record is present.
            2. Perform a query using an invalid project_id.
            3. Validate no records are returned for the node
        """
        # Create a record using sheepdog. Verify record is present.
        record = self.sd_tools.test_records[self.sd_tools.submission_order[0]]
        self.sd_tools.submit_record(record=record)
        # Perform a query using an invalid project_id.
        response = self.sd_tools.query_record_fields(
            record, {"project_id": "NOT-EXIST"}
        )
        # Validate no records are returned for the node
        if len(response["data"][record.node_name]) != 0:
            raise f"Expected no records for {record.node_name}. Response : {response}"

    @pytest.mark.graph_query
    def test_with_path_to_first_to_last_node(self):
        """
        Scenario: Test with_path_to - first to last node
        Steps:
            1. Submit graph data using sheepdog. Verify records are present.
            2. Query path from first node to last node.
            3. Verify first node name is present response.
        """
        logger.info("Submitting test records")
        self.sd_tools.submit_all_test_records()
        # Query path from first node to last node.
        first_node = self.sd_tools.test_records[self.sd_tools.submission_order[0]]
        last_node = self.sd_tools.test_records[self.sd_tools.submission_order[-1]]
        response = self.sd_tools.query_record_with_path_to(first_node, last_node)
        # Verify first node name is present response.
        assert (
            first_node.node_name in response["data"].keys()
        ), "{} not found in response {}".format(first_node.node_name, response)

    @pytest.mark.graph_query
    def test_with_path_to_last_to_first_node(self):
        """
        Scenario: Test with_path_to - last to first node
        Steps:
            1. Submit graph data using sheepdog. Verify records are present.
            2. Query path from last node to first node.
            3. Verify last node name is present response.
        """
        logger.info("Submitting test records")
        self.sd_tools.submit_all_test_records()
        # Query path from last node to first node.
        first_node = self.sd_tools.test_records[self.sd_tools.submission_order[0]]
        last_node = self.sd_tools.test_records[self.sd_tools.submission_order[-1]]
        response = self.sd_tools.query_record_with_path_to(last_node, first_node)
        # Verify last node name is present response.
        assert (
            last_node.node_name in response["data"].keys()
        ), "{} not found in response {}".format(last_node.node_name, response)

    @pytest.mark.skipif(
        skip_consent_code_test(sd_tools),
        reason="Consent Codes not available in dictionary",
    )
    def test_submit_data_record_with_consent_codes(self):
        """
        Scenario: Update file with invalid property
        Steps:
            1. Submit metadata for file node, including consent codes
            2. Verify indexd record was created with the correct consent codes
        """
        indexd = Indexd()

        file_record = self.sd_tools.get_file_record()
        file_record.props["consent_codes"] += ["CC1", "CC2"]
        self.sd_tools.submit_links_for_record(file_record)
        self.sd_tools.submit_record(record=file_record)

        file_record.indexd_guid = self.sd_tools.get_indexd_id_from_graph_id(
            unique_id=file_record.unique_id
        )

        class FileRecord:
            def __init__(self, did: str, props: dict, authz: list) -> None:
                self.did = did
                self.props = props
                self.authz = authz

        file_record_wit_ccs = FileRecord(
            did=file_record.indexd_guid,
            props={
                "md5sum": file_record.props["md5sum"],
                "file_size": file_record.props["file_size"],
            },
            authz=["/consents/CC1", "/consents/CC2"],
        )

        # Verify indexd record was created with the correct consent codes
        response = indexd.get_record(file_record_wit_ccs.did)
        indexd.assert_file_equals(response, file_record_wit_ccs)

    @pytest.mark.indexd
    @pytest.mark.portal
    @pytest.mark.graph_query
    def test_file_landing_page(self, page: LoginPage):
        """
        Scenario: Test file landing page
        Steps:
            1. Submit graph data using sheepdog. Verify records are present.
            2. Create a file record
            3. Get core metadata using record in step 2
            4. Reteive object_id from metadata record recieved
            5. Load metadata page using object_id and verify the elements
            6. Delete file record and delete indexd record
            7. Delete all records. Verify all records are deleted.
        """
        login_page = LoginPage()
        files_landing_page = FilesLandingPage()
        file_record = self.sd_tools.get_file_record()
        self.sd_tools.submit_links_for_record(file_record)
        self.sd_tools.submit_record(record=file_record)
        file_record.indexd_guid = self.sd_tools.get_indexd_id_from_graph_id(
            unique_id=file_record.unique_id
        )
        metadata = self.sd_tools.get_core_metadata(
            file=file_record, user="main_account"
        )
        self.sd_tools.verify_core_metadata_json_contents(
            record=file_record, metadata=metadata
        )

        # Perform login and logout operations using main_account to create a login record for audit service to access
        logger.info("Logging in with mainAcct")
        login_page.go_to(page)
        login_page.login(page)
        files_landing_page.goto_metadata_page(page, metadata.json()["object_id"])
        files_landing_page.verify_metadata_page_elements(page)
        login_page.logout(page)

        self.sd_tools.delete_record(unique_id=file_record.unique_id)

    @pytest.mark.indexd
    @pytest.mark.graph_query
    def test_sheepdog_core_metadata(self):
        """
        Scenario: Test sheepdog core metadata
        Steps:
            1. Submit graph data and verify they are added using main_account
            2. Add file record and verify it is added using main_account
            3. Identify the endpoint of coremetadata using the peregrine version
            4. Get metadata record for the GUID from file record using application/json format
            5. Validate file_name, GUID, Type and data_format of file record matches in metadata
            6. Get metadata record for the GUID from file record using x-bibtex format
            7. Validate file_name, GUID, Type and data_format of file record matches in metadata
        """
        file_record = self.sd_tools.get_file_record()
        self.sd_tools.submit_links_for_record(file_record)
        self.sd_tools.submit_record(record=file_record)
        file_record.indexd_guid = self.sd_tools.get_indexd_id_from_graph_id(
            unique_id=file_record.unique_id
        )
        metadata = self.sd_tools.get_core_metadata(
            file=file_record, user="main_account"
        )
        self.sd_tools.verify_core_metadata_json_contents(
            record=file_record, metadata=metadata
        )

        metadata = self.sd_tools.get_core_metadata(
            file=file_record, user="main_account", format="x-bibtex"
        )
        self.sd_tools.verify_core_metadata_bibtex_contents(
            record=file_record, metadata=metadata
        )

    @pytest.mark.indexd
    @pytest.mark.graph_query
    def test_sheepdog_core_metadata_invalid_object_id(self):
        """
        Scenario: Test sheepdog core metadata invalid object_id
        Steps:
            1. Submit graph data and verify they are added using main_account
            2. Get invalid_file record details and update did with wrong value
            3. Identify the endpoint of coremetadata using the peregrine version
            4. Get metadata record for the GUID from file record using application/json format
            5. Step 4 should fail with 404 error as object/did is not present
            6. Delete all records
        """
        invalid_file_record = self.sd_tools.get_file_record()
        invalid_file_record.props["object_id"] = "invalid_object_id"
        invalid_file_record.indexd_guid = "invalid_object_id"
        metadata = self.sd_tools.get_core_metadata(
            file=invalid_file_record, user="main_account", expected_status=404
        )
        self.sd_tools.see_core_metadata_error(
            metadata=metadata, message='object_id "invalid_object_id" not found'
        )

    @pytest.mark.indexd
    @pytest.mark.graph_query
    def test_sheepdog_core_metadata_no_permission(self):
        """
        Scenario: Test sheepdog core metadata no permission
        Steps:
            1. Submit graph data and verify they are added using main_account
            2. Add file record and verify it is added using main_account
            3. Identify the endpoint of coremetadata using the peregrine version
            4. Get metadata record for the GUID from file record using application/json format and invalid authorization
            5. Step 4 should fail with 401 error as invalid authorization was passed
            6. Verify "Authentication Error: could not parse authorization header" message was recieved
        """
        file_record = self.sd_tools.get_file_record()
        self.sd_tools.submit_links_for_record(file_record)
        self.sd_tools.submit_record(record=file_record)
        file_record.indexd_guid = self.sd_tools.get_indexd_id_from_graph_id(
            unique_id=file_record.unique_id
        )
        metadata = self.sd_tools.get_core_metadata(
            file=file_record,
            user="main_account",
            expected_status=401,
            invalid_authorization=True,
        )
        self.sd_tools.see_core_metadata_error(
            metadata=metadata,
            message="Authentication Error: could not parse authorization header",
        )

    @pytest.mark.indexd
    def test_submit_and_delete_file(self):
        """
        Scenario: Submit and delete file
        Steps:
            1. Submit graph data using sheepdog. Verify records are present.
            2. Create a file record and retrieve record from indexd
               (an indexd record is automatically created when a sheepdog file record is created)
            3. Delete file record and delete indexd record
        """
        indexd = Indexd()
        file_record = self.sd_tools.get_file_record()
        self.sd_tools.submit_links_for_record(file_record)
        self.sd_tools.submit_record(record=file_record)
        file_record.indexd_guid = self.sd_tools.get_indexd_id_from_graph_id(
            unique_id=file_record.unique_id
        )
        record = indexd.get_record(indexd_guid=file_record.indexd_guid)
        rev = indexd.get_rev(record)

        # Deleting file record and indexd record
        self.sd_tools.delete_record(unique_id=file_record.unique_id)
        delete_record = indexd.delete_record(guid=file_record.indexd_guid, rev=rev)
        assert (
            delete_record == 200
        ), f"Failed to delete record {file_record.indexd_guid}"

    @pytest.mark.indexd
    def test_submit_file_with_url(self):
        """
        Scenario: Submit file with URL
        Steps:
            1. Submit graph data using sheepdog. Verify records are present.
            2. Create a file record with URL and retrieve record from indexd
               (an indexd record is automatically created when a sheepdog file record is created)
            3. Delete file record and delete indexd record
        """
        indexd = Indexd()
        test_url = "s3://cdis-presigned-url-test/testdata"
        file_record = self.sd_tools.get_file_record()
        self.sd_tools.submit_links_for_record(file_record)
        file_record.props["urls"] = test_url
        self.sd_tools.submit_record(record=file_record)
        file_record.indexd_guid = self.sd_tools.get_indexd_id_from_graph_id(
            unique_id=file_record.unique_id
        )
        record = indexd.get_record(indexd_guid=file_record.indexd_guid)
        rev = indexd.get_rev(record)

        # Check record and indexd record contents
        indexd.assert_file_equals(record, file_record)

        # Deleting indexd record (sheepdog record is deleted by `teardown_method`)
        delete_record = indexd.delete_record(guid=file_record.indexd_guid, rev=rev)
        assert (
            delete_record == 200
        ), f"Failed to delete record {file_record.indexd_guid}"

    @pytest.mark.indexd
    def test_submit_file_then_update_with_url(self):
        """
        Scenario: Submit file then update with URL
        Steps:
            1. Submit graph data using sheepdog. Verify records are present.
            2. Create a file record and retrieve record from indexd
               (an indexd record is automatically created when a sheepdog file record is created)
            3. Add URL to file record and update file record.
               (the indexd record is automatically updated when its sheepdog file record is updated)
            4. Delete file record and delete indexd record
        """
        indexd = Indexd()
        test_url = "s3://cdis-presigned-url-test/testdata"
        file_record = self.sd_tools.get_file_record()
        self.sd_tools.submit_links_for_record(file_record)
        self.sd_tools.submit_record(record=file_record)
        did = self.sd_tools.get_indexd_id_from_graph_id(unique_id=file_record.unique_id)
        record = indexd.get_record(indexd_guid=did)
        rev = indexd.get_rev(record)

        # Add URL to the record data and update it
        file_record.props["urls"] = test_url
        self.sd_tools.submit_record(record=file_record)
        file_record.indexd_guid = self.sd_tools.get_indexd_id_from_graph_id(
            unique_id=file_record.unique_id
        )
        record = indexd.get_record(indexd_guid=file_record.indexd_guid)
        rev = indexd.get_rev(record)

        # Check record and indexd record contents
        indexd.assert_file_equals(record, file_record)

        # Deleting indexd record (sheepdog record is deleted by `teardown_method`)
        delete_record = indexd.delete_record(guid=file_record.indexd_guid, rev=rev)
        assert (
            delete_record == 200
        ), f"Failed to delete record {file_record.indexd_guid}"
