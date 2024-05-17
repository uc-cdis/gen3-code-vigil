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
from pages.metadata_landing_page import MetadataLandingPage

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


'''def validate_consent_codes():
    """
    Function to check if consent_codes is available in dictionary or not.
    Used to skip test if consent_codes in not available.
    """
    auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
    sd_tools = GraphDataTools(auth=auth, program_name="jnkns", project_code="jenkins")
    metadata = sd_tools.get_file_record()
    if "consent_codes" not in metadata.props.keys():
        return True
    return False'''


class FileNode:
    def __init__(self, did: str, props: dict, authz: list) -> None:
        self.did = did
        self.props = props
        self.authz = authz


@pytest.mark.graph_submission
@pytest.mark.graph_query
class TestGraphSubmitAndQuery:
    @classmethod
    def setup_class(cls):
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        sd_tools.create_program_and_project()

    def teardown_method(self, method):
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        # Load all test records
        sd_tools.load_test_records()
        # Delete all test records
        sd_tools.delete_all_records_in_test_project()

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
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(auth=auth)
        sd_tools.load_test_records()

        logger.info("Submitting test records")
        sd_tools.submit_all_test_records()

        new_records = []
        try:
            logger.info(
                "For each node, query all the properties and check that the response matches"
            )
            for node_name, record in sd_tools.test_records.items():
                primitive_props = [
                    prop
                    for prop in record.props.keys()
                    if type(record.props[prop]) != dict
                ]
                props_str = " ".join(primitive_props)
                query = f'query {{ {node_name} (project_id: "{sd_tools.project_id}") {{ {props_str} }} }}'
                received_data = (
                    sd_tools.graphql_query(query).get("data", {}).get(node_name, [])
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
            record = sd_tools.test_records[node_name]

            logger.info("Query an invalid property")
            query = f'query {{ {node_name} (project_id: "{sd_tools.project_id}") {{ prop_does_not_exist }} }}'
            with pytest.raises(
                Gen3SubmissionQueryError,
                match=f'Cannot query field "prop_does_not_exist" on type "{node_name}".',
            ):
                sd_tools.graphql_query(query)

            logger.info("Query with filter on a string property")
            string_prop = [
                prop for prop in record.props.keys() if type(record.props[prop]) == str
            ][0]
            string_prop_value = record.props[string_prop]
            query = f'query {{ {node_name} (project_id: "{sd_tools.project_id}", {string_prop}: "{string_prop_value}") {{ {string_prop} }} }}'
            received_data = (
                sd_tools.graphql_query(query).get("data", {}).get(node_name, [])
            )
            assert len(received_data) == 1
            assert received_data[0][string_prop] == string_prop_value

            logger.info("Query node count before and after submitting a new record")
            result = sd_tools.query_node_count(node_name)
            count = result.get("data", {}).get(f"_{node_name}_count")
            new_records.append(sd_tools.submit_new_record(node_name))
            result = sd_tools.query_node_count(node_name)
            assert result.get("data", {}).get(f"_{node_name}_count") == count + 1
        finally:
            if new_records:
                sd_tools.delete_records([record.unique_id for record in new_records])
            sd_tools.delete_all_test_records()

    def test_submit_node_unauthenticated(self):
        """
        Scenario: Submit node unauthenticated
        Steps:
            1. Generate an expired token
            2. Create a node with expired token
            3. Creating node should fail
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        # Load all test records
        sd_tools.load_test_records()
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

        # Create a node with expired token
        first_node = sd_tools.test_records[sd_tools.submission_order[0]]
        response = requests.put(
            url=pytest.root_url + "/api/v0/submission/jnkns/jenkins",
            data=json.dumps(first_node.props),
            headers=auth_header,
        )
        assert response.status_code == 401, f"Failed to delete record {response}"

    def test_submit_node_without_parent(self):
        """
        Scenario: Submit node without parent
        Steps:
            1. Create a node using sheepdog. Verify node is present.
            2. Perform a query using an invalid project_id.
            3. Validate length of fields returned for node name is 0
            4. Delete the node created. Verify node is deleted.
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        # Load all test records
        sd_tools.load_test_records()
        # Verify parent node does not exist
        parent_node = sd_tools.test_records[sd_tools.submission_order[0]]
        parent_response = sd_tools.query_record_fields(parent_node)
        # Validate length of fields returned for node name is 0
        if len(parent_response["data"][parent_node.node_name]) != 0:
            logger.error(
                "Found fields for {}. Response : {}".format(
                    parent_node.node_name, parent_response
                )
            )
            raise

        # Attempt to add second node which has a dependency on another node
        second_node = sd_tools.get_record_with_parent()
        try:
            logger.info(sd_tools.submit_record(record=second_node))
        except requests.exceptions.HTTPError as e:
            if e.response.status_code != 400:
                logger.error(f"Expected 400 status code not found. Response: {e}")
                raise

    def test_filter_by_invalid_project_id(self):
        """
        Scenario: Filter by invalid project_id
        Steps:
            1. Create a node using sheepdog. Verify node is present.
            2. Perform a query using an invalid project_id.
            3. Validate length of fields returned for node name is 0
            4. Delete the node created. Verify node is deleted.
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        # Load all test records
        sd_tools.load_test_records()
        # Create a node using sheepdog. Verify node is present.
        record = sd_tools.test_records[sd_tools.submission_order[0]]
        sd_tools.submit_record(record=record)
        # Perform a query using an invalid project_id.
        response = sd_tools.query_record_fields(record, {"project_id": "NOT-EXIST"})
        # Validate length of fields returned for node name is 0
        if len(response["data"][record.node_name]) != 0:
            logger.error(
                "Found fields for {}. Response : {}".format(record.node_name, response)
            )
            raise
        sd_tools.delete_record(unique_id=record.unique_id)

    def test_with_path_to_first_to_last_node(self):
        """
        Scenario: Test with_path_to - first to last node
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Query path from first node to last node.
            3. Verify first node name is present response.
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        # Load all test records
        sd_tools.load_test_records()
        logger.info("Submitting test records")
        sd_tools.submit_all_test_records()
        # Query path from first node to last node.
        first_node = sd_tools.test_records[sd_tools.submission_order[0]]
        last_node = sd_tools.test_records[sd_tools.submission_order[-1]]
        response = sd_tools.query_record_with_path_to(first_node, last_node)
        # Verify first node name is present response.
        assert (
            first_node.node_name in response["data"].keys()
        ), "{} not found in response {}".format(first_node.node_name, response)

    def test_with_path_to_last_to_first_node(self):
        """
        Scenario: Test with_path_to - last to first node
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Query path from last node to first node.
            3. Verify last node name is present response.
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        # Load all test records
        sd_tools.load_test_records()
        logger.info("Submitting test records")
        sd_tools.submit_all_test_records()
        # Query path from last node to first node.
        first_node = sd_tools.test_records[sd_tools.submission_order[0]]
        last_node = sd_tools.test_records[sd_tools.submission_order[-1]]
        response = sd_tools.query_record_with_path_to(last_node, first_node)
        # Verify last node name is present response.
        assert (
            last_node.node_name in response["data"].keys()
        ), "{} not found in response {}".format(last_node.node_name, response)

    # @pytest.mark.skipif(
    #    validate_consent_codes(), reason="Consent Codes not available in dictionary"
    # )
    def test_submit_data_node_with_consent_codes(self):
        """
        Scenario: Update file with invalid property
        Steps:
            1. Retrieve records from Indexd
            2. Delete all records retrieved.
            3. Submit metatdata for file node, including consent codes
            4. Verify indexd record was created with the correct consent codes
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        indexd_auth = Gen3Auth(refresh_token=pytest.api_keys["indexing_account"])
        gen3_indexd = Gen3Index(auth_provider=indexd_auth)
        indexd = Indexd()
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        # Load all test records without records having category ending with _file
        sd_tools.load_test_records(submit_file_records=False)
        records = gen3_indexd.get_all_records()

        # Delete indexd records
        for record in records:
            gen3_indexd.delete_record(guid=record["did"])

        # Submit metatdata for file node, including consent codes
        file_record = sd_tools.get_file_record()
        file_record.props["consent_codes"] += ["CC1", "CC2"]
        sd_tools.submit_links_for_node(record=file_record)
        sd_tools.submit_record(record=file_record)

        file_record.indexd_guid = sd_tools.get_indexd_id_from_graph_id(
            unique_id=file_record.unique_id
        )

        file_node_wit_ccs = FileNode(
            did=file_record.indexd_guid,
            props={
                "md5sum": file_record.props["md5sum"],
                "file_size": file_record.props["file_size"],
            },
            authz=["/consents/CC1", "/consents/CC2"],
        )

        # Verify indexd record was created with the correct consent codes
        response = indexd.get_record(file_node_wit_ccs.did)
        indexd.file_equals(response, file_node_wit_ccs)

    @pytest.mark.indexd
    @pytest.mark.portal
    def test_core_metadata_page(self, page: LoginPage):
        """
        Scenario: Test core metadata page
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Create a file node
            3. Get core metadata using node in step 2
            4. Reteive object_id from metadata record recieved
            5. Load metadata page using object_id and verify the elements
            6. Delete file node and delete indexd record
            7. Delete all nodes. Verify all nodes are deleted.
        """
        login_page = LoginPage()
        metadata_landing_page = MetadataLandingPage()
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        # Load all test records without records having category ending with _file
        sd_tools.load_test_records(submit_file_records=False)
        logger.info("Submitting test records")
        sd_tools.submit_all_test_records()
        file_record = sd_tools.get_file_record()
        sd_tools.submit_record(record=file_record)
        file_record.indexd_guid = sd_tools.get_indexd_id_from_graph_id(
            unique_id=file_record.unique_id
        )
        metadata = sd_tools.get_core_metadata(file=file_record, user="main_account")
        sd_tools.verify_metadata_json_contents(record=file_record, metadata=metadata)

        # Perform login and logout operations using main_account to create a login record for audit service to access
        logger.info("Logging in with mainAcct")
        login_page.go_to(page)
        login_page.login(page)
        metadata_landing_page.goto_metadata_page(page, metadata.json()["object_id"])
        metadata_landing_page.verify_metadata_page_elements(page)
        login_page.logout(page)

        sd_tools.delete_record(unique_id=file_record.unique_id)

    # TODO move indexd tests to a new test suite and use pytest.mark.graph_submission/query
    # when needed. May create issues with parallel tests updating graph data at the same time
    @pytest.mark.indexd
    # TODO rename "core metadata" references, call it something like "test_file_landing_page"
    def test_core_metadata(self):
        """
        Scenario: Test core metadata
        Steps:
            1. Create nodes and verify they are added using main_account
            2. Add file node and verify it is added using main_account
            3. Identify the endpoint of coremetadata using the peregrine version
            4. Get metadata record for the GUID from file node using application/json format
            5. Validate file_name, GUID, Type and data_format of file node matches in metadata
            6. Get metadata record for the GUID from file node using x-bibtex format
            7. Validate file_name, GUID, Type and data_format of file node matches in metadata
            8. Delete all nodes
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        # Load all test records without records having category ending with _file
        sd_tools.load_test_records(submit_file_records=False)
        logger.info("Submitting test records")
        sd_tools.submit_all_test_records()

        file_record = sd_tools.get_file_record()
        sd_tools.submit_record(record=file_record)
        file_record.indexd_guid = sd_tools.get_indexd_id_from_graph_id(
            unique_id=file_record.unique_id
        )
        metadata = sd_tools.get_core_metadata(file=file_record, user="main_account")
        sd_tools.verify_metadata_json_contents(record=file_record, metadata=metadata)

        metadata = sd_tools.get_core_metadata(
            file=file_record, user="main_account", format="x-bibtex"
        )
        sd_tools.verify_metadata_bibtex_contents(record=file_record, metadata=metadata)

        sd_tools.delete_record(unique_id=file_record.unique_id)

    @pytest.mark.indexd
    def test_core_metadata_invalid_object_id(self):
        """
        Scenario: Test core metadata invalid object_id
        Steps:
            1. Create nodes and verify they are added using main_account
            2. Get invalid_file node details and update did with wrong value
            3. Identify the endpoint of coremetadata using the peregrine version
            4. Get metadata record for the GUID from file node using application/json format
            5. Step 4 should fail with 404 error as object/did is not present
            6. Delete all nodes
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        # Load all test records without records
        sd_tools.load_test_records()
        invalid_file_record = sd_tools.get_file_record()
        invalid_file_record.props["object_id"] = "invalid_object_id"
        invalid_file_record.indexd_guid = "invalid_object_id"
        metadata = sd_tools.get_core_metadata(
            file=invalid_file_record, user="main_account", expected_status=404
        )
        sd_tools.see_core_metadata_error(
            metadata=metadata, message='object_id "invalid_object_id" not found'
        )

    @pytest.mark.indexd
    def test_core_metadata_no_permission(self):
        """
        Scenario: Test core metadata no permission
        Steps:
            1. Create nodes and verify they are added using main_account
            2. Add file node and verify it is added using main_account
            3. Identify the endpoint of coremetadata using the peregrine version
            4. Get metadata record for the GUID from file node using application/json format and invalid authorization
            5. Step 4 should fail with 401 error as invalid authorization was passed
            6. Verify "Authentication Error: could not parse authorization header" message was recieved
            7. Delete all nodes
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        # Load all test records without records having category ending with _file
        sd_tools.load_test_records(submit_file_records=False)
        logger.info("Submitting test records")
        sd_tools.submit_all_test_records()

        file_record = sd_tools.get_file_record()
        sd_tools.submit_record(record=file_record)
        file_record.indexd_guid = sd_tools.get_indexd_id_from_graph_id(
            unique_id=file_record.unique_id
        )
        metadata = sd_tools.get_core_metadata(
            file=file_record,
            user="main_account",
            expected_status=401,
            invalid_authorization=True,
        )
        sd_tools.see_core_metadata_error(
            metadata=metadata,
            message="Authentication Error: could not parse authorization header",
        )

        sd_tools.delete_record(unique_id=file_record.unique_id)

    @pytest.mark.indexd
    def test_submit_and_delete_file(self):
        """
        Scenario: Submit and delete file
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Create a file node and retrieve record from indexd
            3. Delete file node and delete indexd record
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        indexd = Indexd()
        # Load all test records without records having category ending with _file
        sd_tools.load_test_records(submit_file_records=False)
        logger.info("Submitting test records")
        sd_tools.submit_all_test_records()

        # Adding file node and retrieveing indexd record
        file_record = sd_tools.get_file_record()
        sd_tools.submit_record(record=file_record)
        file_record.indexd_guid = sd_tools.get_indexd_id_from_graph_id(
            unique_id=file_record.unique_id
        )
        record = indexd.get_record(indexd_guid=file_record.indexd_guid)
        rev = indexd.get_rev(record)

        # Deleting file node and indexd record
        sd_tools.delete_record(unique_id=file_record.unique_id)
        delete_record = indexd.delete_record(guid=file_record.indexd_guid, rev=rev)
        assert (
            delete_record == 200
        ), f"Failed to delete record {file_record.indexd_guid}"

    @pytest.mark.indexd
    def test_submit_file_with_url(self):
        """
        Scenario: Submit file with URL
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Create a file node with URL and retrieve record from indexd
            3. Delete file node and delete indexd record
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        indexd = Indexd()
        test_url = "s3://cdis-presigned-url-test/testdata"
        # Load all test records without records having category ending with _file
        sd_tools.load_test_records(submit_file_records=False)
        logger.info("Submitting test records")
        sd_tools.submit_all_test_records()

        # Adding file node and retrieveing indexd record
        file_record = sd_tools.get_file_record()
        file_record.props["urls"] = test_url
        sd_tools.submit_record(record=file_record)
        file_record.indexd_guid = sd_tools.get_indexd_id_from_graph_id(
            unique_id=file_record.unique_id
        )
        record = indexd.get_record(indexd_guid=file_record.indexd_guid)
        rev = indexd.get_rev(record)

        # Check node and indexd record contents
        indexd.file_equals(record, file_record)

        # Deleting file node and indexd record
        sd_tools.delete_record(unique_id=file_record.unique_id)
        delete_record = indexd.delete_record(guid=file_record.indexd_guid, rev=rev)
        assert (
            delete_record == 200
        ), f"Failed to delete record {file_record.indexd_guid}"

    @pytest.mark.indexd
    def test_submit_file_then_update_with_url(self):
        """
        Scenario: Submit file then update with URL
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Create a file node and retrieve record from indexd
            3. Add URL to file node and update file node.
            4. Delete file node and delete indexd record
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        indexd = Indexd()
        test_url = "s3://cdis-presigned-url-test/testdata"
        # Load all test records without records having category ending with _file
        sd_tools.load_test_records(submit_file_records=False)
        logger.info("Submitting test records")
        sd_tools.submit_all_test_records()

        # Adding file node and retrieveing indexd record without URL
        file_record = sd_tools.get_file_record()
        sd_tools.submit_record(record=file_record)
        did = sd_tools.get_indexd_id_from_graph_id(unique_id=file_record.unique_id)
        record = indexd.get_record(indexd_guid=did)
        rev = indexd.get_rev(record)

        # Add URL to the node data and update it
        file_record.props["urls"] = test_url
        sd_tools.submit_record(record=file_record)
        file_record.indexd_guid = sd_tools.get_indexd_id_from_graph_id(
            unique_id=file_record.unique_id
        )
        record = indexd.get_record(indexd_guid=file_record.indexd_guid)
        rev = indexd.get_rev(record)

        # Check node and indexd record contents
        indexd.file_equals(record, file_record)

        # Deleting file node and indexd record
        sd_tools.delete_record(unique_id=file_record.unique_id)
        delete_record = indexd.delete_record(guid=file_record.indexd_guid, rev=rev)
        assert (
            delete_record == 200
        ), f"Failed to delete record {file_record.indexd_guid}"
