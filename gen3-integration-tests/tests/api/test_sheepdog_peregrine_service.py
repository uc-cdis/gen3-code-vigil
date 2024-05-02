"""
SHEEPDOG & PEREGRINE SERVICE
"""
import json
import os
import pytest
import requests

from cdislogging import get_logger
from services.indexd import Indexd
from services.peregrine import Peregrine
from services.graph import GraphDataTools
from utils.gen3_admin_tasks import create_expired_token
from gen3.auth import Gen3Auth
from gen3.submission import Gen3SubmissionQueryError

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.sheepdog
class TestSheepdogPeregrineService:
    @classmethod
    def setup_class(cls):
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        sd_tools.delete_nodes()

    def teardown_method(self, method):
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        sd_tools.delete_nodes()

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
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        # Generate an expired token
        res = create_expired_token(
            pytest.namespace, "fence", "1", "cdis.autotest@gmail.com"
        )
        res = res.splitlines()[-1].strip()
        auth_header = {
            "Accept": "application/json",
            "Authorization": f"bearer {res}",
            "Content-Type": "application/json",
        }

        # Create a node with expired token
        response = requests.put(
            url=pytest.root_url + "/api/v0/submission/jnkns/jenkins2",
            data=json.dumps(sd_tools.get_first_node().props),
            headers=auth_header,
        )
        assert response.status_code == 401, f"Failed to delete record {response}"

    def test_submit_and_delete_node(self):
        """
        Scenario: Submit and delete node
        Steps:
            1. Create a node using sheepdog. Verify node is present.
            2. Delete the node created. Verify node is deleted.
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        node = sd_tools.get_first_node()
        sd_tools._submit_record(record=node)
        sd_tools._delete_record(unique_id=node.unique_id)

    def test_submit_and_delete_node_path(self):
        """
        Scenario: Submit and delete node path
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Deleted the nodes. Verify nodes are deleted.
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        nodes = sd_tools.get_path_to_file()
        # Create nodes using sheepdog. Verify nodes are present.
        for key, val in nodes.items():
            sd_tools._submit_record(record=val)
        sd_tools.delete_nodes()

    @pytest.mark.peregrine
    def test_make_simple_query(self):
        """
        Scenario: Make simple query
        Steps:
            1. Create a node using sheepdog. Verify node is present.
            2. Perform a simple query to retieve the record created.
            3. Delete the node created. Verify node is deleted.
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        peregrine = Peregrine()
        # Create a node using sheepdog. Verify node is present.
        node = sd_tools.get_first_node()
        sd_tools._submit_record(record=node)
        # Create a node using sheepdog. Verify node is present.
        queryToSubmit = "query Test { alias1: " + node.props["type"] + " { id } }"
        response = peregrine.query(queryToSubmit, {}, "main_account")
        data = response.json()["data"]
        if "alias1" not in data or len(data["alias1"]) != 1:
            logger.error(
                "Either alias1 is missing or exactly 1 id wasn't found. Response: {}".format(
                    data
                )
            )
            raise
        sd_tools._delete_record(unique_id=node.unique_id)

    @pytest.mark.peregrine
    def test_query_all_node_fields(self):
        """
        Scenario: Query all node fields
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Query nodes information using peregrine
            3. Validate results of nodes with results from peregrine
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        nodes = sd_tools.get_path_to_file()
        peregrine = Peregrine()
        # Create nodes using sheepdog. Verify nodes are present.
        for key, val in nodes.items():
            sd_tools._submit_record(record=val)
        results = {}
        for key, val in nodes.items():
            # Query nodes information using peregrine
            query_to_submit = peregrine.query_to_submit(val)
            query_results = sd_tools.graphql_query(query_text=query_to_submit)
            # Validate results of nodes with results from peregrine
            for parameter, value in query_results["data"][key][0].items():
                if val.props[parameter] != value:
                    logger.info(
                        "Result from Peregrine: {}".format(
                            results[key].json()["data"][key]
                        )
                    )
                    logger.info("Node data: {}".format(val.props))
                    logger.error(
                        "{} in results don't match with node data".format(parameter)
                    )
                    raise

    '''@pytest.mark.skip("Test case is broken")
    @pytest.mark.peregrine
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
        sd_tools = GraphDataTools(auth=auth, program_name="jnkns", project_code="jenkins2")
        sheepdog = Sheepdog(program="jnkns", project="jenkins2")
        peregrine = Peregrine()
        # Verify parent node does not exist
        parentNode = nodes.get_first_node()
        parentResponse = peregrine.query_node_fields(parentNode)
        if len(parentResponse.json()["data"][parentNode["name"]]) != 0:
            logger.error(
                "Found fields for {}. Response : {}".format(
                    parentNode["name"], parentResponse.json()
                )
            )
            raise

        # Attempt to add second node
        secondNode = sheepdog.add_node(
            nodes.get_second_node(), "main_account", validate_node=False
        )
        logger.info(secondNode)
        if secondNode["addRes"]["code"] != 400:
            logger.error(
                "Found status which was not 400. Response : {}".format(
                    secondNode.json()
                )
            )
            raise'''

    @pytest.mark.peregrine
    def test_query_on_invalid_field(self):
        """
        Scenario: Query on invalid field
        Steps:
            1. Get type field value from First node
            2. Perform a simple query using an invalid field
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        invalidField = "abcdef"
        # Get type field value from First node
        nodeType = sd_tools.get_first_node().props["type"]
        # Perform a simple query using an invalid field
        query_to_submit = "{ " + nodeType + "{ " + invalidField + "}}"
        try:
            sd_tools.graphql_query(query_text=query_to_submit)
        except Gen3SubmissionQueryError as e:
            logger.info(f"{e}")
            if (
                '[\'Cannot query field "{}" on type "{}".\']'.format(
                    invalidField, nodeType
                )
                != f"{e}"
            ):
                logger.error(
                    'Cannot query field "{}" on type "{}". entry wasn\'t found. Response : {}'.format(
                        invalidField, nodeType, f"{e}"
                    )
                )
                raise

    @pytest.mark.peregrine
    def test_filter_query_by_string_attribute(self):
        """
        Scenario: Filter query by string attribute
        Steps:
            1. Get a property from Node data which is a string attribute
            2. Perform a query using the the property retieved in step 1
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        nodes = sd_tools.get_path_to_file()
        # Create nodes using sheepdog. Verify nodes are present.
        for key, val in nodes.items():
            sd_tools._submit_record(record=val)
        # Get field of type string from first node
        first_node = sd_tools.get_first_node()
        test_field = sd_tools.get_field_of_type(first_node, str)
        # Perform a query using the the property retieved in step 1
        query_to_submit = (
            "{"
            + first_node.node_name
            + " ("
            + test_field
            + ': "'
            + first_node.props[test_field]
            + '") {    id  }}'
        )
        response = sd_tools.graphql_query(query_text=query_to_submit)
        assert (
            first_node.node_name in response["data"].keys()
        ), "{} not found in response {}".format(first_node.node_name, response)

    @pytest.mark.peregrine
    def test_field_count_filter(self):
        """
        Scenario: Test _[field]_count filter
        Steps:
            1. Count the number of each node type before creating nodes
            2. Create nodes using sheepdog. Verify nodes are present.
            3. Count the number of each node type after creating nodes
            4. Count of each node type should get incremented by 1
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        previous_counts = {}
        new_counts = {}
        nodes = sd_tools.get_path_to_file()

        # Count number of each node type
        for key, val in nodes.items():
            previous_counts[val.node_name] = sd_tools.query_node_count(val.node_name)

        # Create nodes using sheepdog. Verify nodes are present.
        for key, val in nodes.items():
            sd_tools._submit_record(record=val)

        # Count number of each node type
        for key, val in nodes.items():
            new_counts[val.node_name] = sd_tools.query_node_count(val.node_name)

        for key, val in new_counts.items():
            # Check node count has increased by 1
            if (
                new_counts[key]["data"][f"_{key}_count"]
                != previous_counts[key]["data"][f"_{key}_count"] + 1
            ):
                logger.info("Counts before adding node : {}".format(previous_counts))
                logger.info("Counts after adding node : {}".format(new_counts))
                logger.error("Node count hasn't increased by 1 for {}".format(key))
                raise

    '''@pytest.mark.wip("Looks like a duplicate test case")
    @pytest.mark.peregrine
    def test_filter_by_project_id(self):
        """
        Scenario: Filter by project_id
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Perform a query using an project_id.
            3. Validate length of fields returned for node name is present.
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(auth=auth, program_name="jnkns", project_code="jenkins2")
        sheepdog = Sheepdog(program="jnkns", project="jenkins2")
        peregrine = Peregrine()
        # Create nodes using sheepdog. Verify nodes are present.
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")
        results = {}
        filters = {"project_id": "jnkns-jenkins2"}
        for key, val in nodes_dict.items():
            results[key] = peregrine.query_node_fields(val, filters)
            for parameter, value in results[key].json()["data"][key][0].items():
                if nodes_dict[key]["data"][parameter] != value:
                    logger.info(
                        "Result from Peregrine: {}".format(
                            results[key].json()["data"][key]
                        )
                    )
                    logger.info("Node data: {}".format(nodes_dict[key]))
                    logger.error(
                        "{} in results don't match with node data".format(parameter)
                    )
                    raise'''

    @pytest.mark.peregrine
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
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        peregrine = Peregrine()
        # Create a node using sheepdog. Verify node is present.
        node = sd_tools.get_first_node()
        sd_tools._submit_record(record=node)
        # Perform a query using an invalid project_id.
        filters = {"project_id": "NOT-EXIST"}
        query_to_submit = peregrine.query_to_submit(node, filters)
        response = sd_tools.graphql_query(query_text=query_to_submit)
        # Validate length of fields returned for node name is 0
        if len(response["data"][node.node_name]) != 0:
            logger.error(
                "Found fields for {}. Response : {}".format(node.node_name, response)
            )
            raise
        sd_tools._delete_record(unique_id=node.unique_id)

    @pytest.mark.peregrine
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
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        peregrine = Peregrine()
        nodes = sd_tools.get_path_to_file()
        # Create nodes using sheepdog. Verify nodes are present.
        for key, val in nodes.items():
            sd_tools._submit_record(record=val)
        # Query path from first node to last node.
        first_node = sd_tools.get_first_node()
        last_node = sd_tools.get_last_node()
        query_to_submit = peregrine.query_with_path_to(first_node, last_node)
        response = sd_tools.graphql_query(query_text=query_to_submit)
        # Verify first node name is present response.
        assert (
            first_node.node_name in response["data"].keys()
        ), "{} not found in response {}".format(first_node.node_name, response)

    @pytest.mark.peregrine
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
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        peregrine = Peregrine()
        nodes = sd_tools.get_path_to_file()
        # Create nodes using sheepdog. Verify nodes are present.
        for key, val in nodes.items():
            sd_tools._submit_record(record=val)
        # Query path from last node to first node.
        first_node = sd_tools.get_first_node()
        last_node = sd_tools.get_last_node()
        query_to_submit = peregrine.query_with_path_to(last_node, first_node)
        response = sd_tools.graphql_query(query_text=query_to_submit)
        # Verify last node name is present response.
        assert (
            last_node.node_name in response["data"].keys()
        ), "{} not found in response {}".format(last_node.node_name, response)

    '''@pytest.mark.skip("Test case is broken")
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
        sd_tools = GraphDataTools(auth=auth, program_name="jnkns", project_code="jenkins2")
        indexd = Indexd()
        sheepdog = Sheepdog(program="jnkns", project="jenkins2")
        records = indexd.get_all_records()

        # Delete indexd records
        for record in records:
            delete_resp = indexd.delete_record(guid=record["did"], rev=record["rev"])
            assert delete_resp == 200, f"Failed to delete record {record['did']}"

        # Submit metatdata for file node, including consent codes
        sheepdog_res = nodes.submit_graph_and_file_metadata(
            sheepdog, None, None, None, None, ["CC1", "CC2"]
        )

        file_node_wit_ccs = {
            "did": sheepdog_res["did"],
            "authz": ["/consents/CC1", "/consents/CC2"],
            "data": {
                "md5sum": sheepdog_res["data"]["md5sum"],
                "file_size": sheepdog_res["data"]["file_size"],
            },
        }

        # Verify indexd record was created with the correct consent codes
        response = indexd.get_record(file_node_wit_ccs["did"])
        indexd.file_equals(response, file_node_wit_ccs)'''

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
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        indexd = Indexd()
        nodes = sd_tools.get_path_to_file()
        # Adding all nodes except file node
        for key, val in nodes.items():
            sd_tools._submit_record(record=val)

        # Adding file node and retrieveing indexd record
        node = sd_tools.get_file_node()
        sd_tools._submit_record(record=node)
        node.indexd_guid = sd_tools.get_did_from_file_id(guid=node.unique_id)
        record = indexd.get_record(indexd_guid=node.indexd_guid)
        rev = indexd.get_rev(record)

        # Deleting file node and indexd record
        sd_tools._delete_record(unique_id=node.unique_id)
        delete_record = indexd.delete_record(guid=node.indexd_guid, rev=rev)
        assert delete_record == 200, f"Failed to delete record {node.indexd_guid}"

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
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        indexd = Indexd()
        test_url = "s3://cdis-presigned-url-test/testdata"
        nodes = sd_tools.get_path_to_file()
        # Adding all nodes except file node
        for key, val in nodes.items():
            sd_tools._submit_record(record=val)

        # Adding file node and retrieveing indexd record
        node = sd_tools.get_file_node()
        node.props["urls"] = test_url
        sd_tools._submit_record(record=node)
        node.indexd_guid = sd_tools.get_did_from_file_id(guid=node.unique_id)
        record = indexd.get_record(indexd_guid=node.indexd_guid)
        rev = indexd.get_rev(record)

        # Check node and indexd record contents
        indexd.file_equals(record, node)

        # Deleting file node and indexd record
        sd_tools._delete_record(unique_id=node.unique_id)
        delete_record = indexd.delete_record(guid=node.indexd_guid, rev=rev)
        assert delete_record == 200, f"Failed to delete record {node.indexd_guid}"

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
            auth=auth, program_name="jnkns", project_code="jenkins2"
        )
        indexd = Indexd()
        test_url = "s3://cdis-presigned-url-test/testdata"
        nodes = sd_tools.get_path_to_file()
        # Adding all nodes except file node
        for key, val in nodes.items():
            sd_tools._submit_record(record=val)

        # Adding file node and retrieveing indexd record without URL
        node = sd_tools.get_file_node()
        sd_tools._submit_record(record=node)
        did = sd_tools.get_did_from_file_id(guid=node.unique_id)
        record = indexd.get_record(indexd_guid=did)
        rev = indexd.get_rev(record)

        # Add URL to the node data and update it
        node.props["urls"] = test_url
        sd_tools._submit_record(record=node)
        node.indexd_guid = sd_tools.get_did_from_file_id(guid=node.unique_id)
        record = indexd.get_record(indexd_guid=node.indexd_guid)
        rev = indexd.get_rev(record)

        # Check node and indexd record contents
        indexd.file_equals(record, node)

        # Deleting file node and indexd record
        sd_tools._delete_record(unique_id=node.unique_id)
        delete_record = indexd.delete_record(guid=node.indexd_guid, rev=rev)
        assert delete_record == 200, f"Failed to delete record {node.indexd_guid}"

    '''@pytest.mark.wip("This test case is broken due to bug in sheepdog")
    def test_submit_file_invalid_property(self):
        """
        Scenario: Submit file invalid property
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Create a file node with an invalid property
            3. Validate node wasn't added
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(auth=auth, program_name="jnkns", project_code="jenkins2")
        sheepdog = Sheepdog(program="jnkns", project="jenkins2")

        # Adding all nodes except file node
        sheepdog.add_nodes(np.get_path_to_file(), "main_account")

        # Adding invalid property to node and attempting to create record
        file_node = np.get_file_node()
        file_node["data"]["file_size"] = "hello"
        node = sheepdog.add_node(
            file_node, "main_account", validate_node=False, invalid_property=True
        )
        logger.info(node)

        # Need to insert check to validate "Internal server error. Sorry, something unexpected went wrong!" is part of transactional_errors

    @pytest.mark.indexd
    @pytest.mark.wip("This test case is broken due to bug in sheepdog")
    def test_update_file_with_invalid_property(self):
        """
        Scenario: Update file with invalid property
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Create a file node and retrieve record from indexd
            3. Update file node with invalid property and try updating node
            4. Validate node wasn't updated
            5. Delete file node and delete indexd record
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(auth=auth, program_name="jnkns", project_code="jenkins2")
        sheepdog = Sheepdog(program="jnkns", project="jenkins2")
        indexd = Indexd()
        # Adding all nodes except file node
        sheepdog.add_nodes(np.get_path_to_file(), "main_account")

        # Adding file node and retrieveing indexd record
        file_node = np.get_file_node()
        node = sheepdog.add_node(file_node, "main_account")
        record = indexd.get_record(indexd_guid=node["did"])
        rev = indexd.get_rev(record)

        # Add invalid property to the node data and update it
        file_node["data"]["file_size"] = "hello"
        node = sheepdog.update_node(
            file_node, "main_account", validate_node=False, invalid_property=True
        )
        logger.info(node)

        # Deleting file node and indexd record
        sheepdog.delete_node(node, "main_account")
        delete_record = indexd.delete_record(guid=node["did"], rev=rev)
        assert delete_record == 200, f"Failed to delete record {node['did']}"'''

    # Need to insert check to validate "Internal server error. Sorry, something unexpected went wrong!" is part of transactional_errors
