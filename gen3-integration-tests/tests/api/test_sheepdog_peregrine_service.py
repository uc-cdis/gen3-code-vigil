"""
SHEEPDOG & PEREGRINE SERVICE
"""
import json
import os
import pytest
import requests

from cdislogging import get_logger
from services.coremetadata import CoreMetaData
from services.indexd import Indexd
from services.peregrine import Peregrine
from services.sheepdog import Sheepdog
from utils import nodes
from utils.gen3_admin_tasks import create_expired_token, kube_setup_service
from utils.test_setup import create_program_project, generate_graph_data

from gen3.auth import Gen3Auth
from gen3.index import Gen3Index

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.sheepdog
class TestSheepdogPeregrineService:
    @classmethod
    def setup_class(cls):
        logger.info("Generating data")
        generate_graph_data()
        logger.info("Create/Update program and project")
        create_program_project()
        logger.info("Restarting indexd service")
        assert kube_setup_service(pytest.namespace, "indexd")

    def setup_method(self, method):
        sdp = Sheepdog()
        # Delete all existing nodes prior to running the test cases
        logger.info("Deleting any existing nodes before test case execution")
        sdp.delete_all_nodes()

    def teardown_method(self, method):
        sdp = Sheepdog()
        # Delete all nodes post running the test cases
        logger.info("Deleting any existing nodes after test case execution")
        sdp.delete_all_nodes()

    def test_submit_node_unauthenticated(self):
        """
        Scenario: Submit node unauthenticated
        Steps:
            1. Generate an expired token
            2. Create a node with expired token
            3. Creating node should fail
        """
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
            url=pytest.root_url + "/api/v0/submission/jnkns/jenkins",
            data=json.dumps(nodes.get_first_node()),
            headers=auth_header,
        )
        assert response.status_code == 401, f"Failed to delete record {response.json()}"

    def test_submit_and_delete_node(self):
        """
        Scenario: Submit and delete node
        Steps:
            1. Create a node using sheepdog. Verify node is present.
            2. Delete the node created. Verify node is deleted.
        """
        sheepdog = Sheepdog()
        node = sheepdog.add_node(nodes.get_first_node(), "main_account")
        sheepdog.delete_node(node, "main_account")

    def test_submit_and_delete_node_path(self):
        """
        Scenario: Submit and delete node path
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Deleted the nodes. Verify nodes are deleted.
        """
        sheepdog = Sheepdog()
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")
        sheepdog.delete_nodes(nodes_dict, "main_account")

    @pytest.mark.peregrine
    def test_make_simple_query(self):
        """
        Scenario: Make simple query
        Steps:
            1. Create a node using sheepdog. Verify node is present.
            2. Perform a simple query to retieve the record created.
            3. Delete the node created. Verify node is deleted.
        """
        sheepdog = Sheepdog()
        peregrine = Peregrine()
        # Create a node using sheepdog. Verify node is present.
        node = sheepdog.add_node(nodes.get_first_node(), "main_account")
        # Create a node using sheepdog. Verify node is present.
        queryToSubmit = "query Test { alias1: " + node["data"]["type"] + " { id } }"
        response = peregrine.query(queryToSubmit, {}, "main_account")
        data = response.json()["data"]
        if "alias1" not in data or len(data["alias1"]) != 1:
            logger.error(
                "Either alias1 is missing or exactly 1 id wasn't found. Response: {}".format(
                    data
                )
            )
            raise
        # Create a node using sheepdog. Verify node is present.
        sheepdog.delete_node(node, "main_account")

    @pytest.mark.peregrine
    def test_query_all_node_fields(self):
        """
        Scenario: Query all node fields
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Query nodes information using peregrine
            3. Validate results of nodes with results from peregrine
            4. Delete the node created. Verify node is deleted.
        """
        sheepdog = Sheepdog()
        peregrine = Peregrine()
        # Create nodes using sheepdog. Verify nodes are present.
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")
        results = {}
        for key, val in nodes_dict.items():
            # Query nodes information using peregrine
            results[key] = peregrine.query_node_fields(val)
            # Validate results of nodes with results from peregrine
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
                    raise
        # Delete the node created. Verify node is deleted.
        sheepdog.delete_nodes(nodes_dict, "main_account")

    @pytest.mark.skip("Test case is broken")
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
        sheepdog = Sheepdog()
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
            raise

    @pytest.mark.peregrine
    def test_query_on_invalid_field(self):
        """
        Scenario: Query on invalid field
        Steps:
            1. Get type field value from First node
            2. Perform a simple query using an invalid field
        """
        peregrine = Peregrine()
        invalidField = "abcdef"
        # Get type field value from First node
        nodeType = nodes.get_first_node()["data"]["type"]
        # Perform a simple query using an invalid field
        queryToSubmit = "{ " + nodeType + "{ " + invalidField + "}}"
        response = peregrine.query(queryToSubmit, {}, "main_account").json()
        if (
            'Cannot query field "{}" on type "{}".'.format(invalidField, nodeType)
            != response["errors"][0]
        ):
            logger.error(
                'Cannot query field "{}" on type "{}". entry wasn\'t found. Response : {}'.format(
                    invalidField, nodeType, response
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
        sheepdog = Sheepdog()
        peregrine = Peregrine()
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")

        # Get field of type string from first node
        first_node = nodes.get_first_node()
        test_field = nodes.get_field_of_type(first_node, str)
        # Perform a query using the the property retieved in step 1
        query_to_submit = (
            "{"
            + first_node["name"]
            + " ("
            + test_field
            + ': "'
            + first_node["data"][test_field]
            + '") {    id  }}'
        )
        response = peregrine.query(query_to_submit, {}, "main_account")
        try:
            if first_node["name"] in response.json()["data"].keys():
                logger.info(response.json())
        except:
            logger.error(
                "{} not found in response {}".format(
                    first_node["name"], response.json()
                )
            )
            raise
        sheepdog.delete_nodes(nodes_dict, "main_account")

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
        sheepdog = Sheepdog()
        peregrine = Peregrine()
        previous_counts = {}
        new_counts = {}
        # Count number of each node type
        for key, val in nodes.get_path_to_file().items():
            type_count = "_{}_count".format(val["name"])
            previous_counts[val["name"]] = peregrine.query_count(type_count).json()[
                "data"
            ][type_count]

        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")
        for key, val in nodes.get_path_to_file().items():
            type_count = "_{}_count".format(val["name"])
            new_counts[val["name"]] = peregrine.query_count(type_count).json()["data"][
                type_count
            ]

        for key, val in new_counts.items():
            # Check node count has increased by 1
            if new_counts[key] != previous_counts[key] + 1:
                logger.info("Counts before adding node : {}".format(previous_counts))
                logger.info("Counts after adding node : {}".format(new_counts))
                logger.error("Node count hasn't increased by 1 for {}".format(key))
                raise
        sheepdog.delete_nodes(nodes_dict, "main_account")

    @pytest.mark.peregrine
    def test_filter_by_project_id(self):
        """
        Scenario: Filter by project_id
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Perform a query using an project_id.
            3. Validate length of fields returned for node name is present.
            4. Delete the nodes created. Verify nodes are deleted.
        """
        sheepdog = Sheepdog()
        peregrine = Peregrine()
        # Create nodes using sheepdog. Verify nodes are present.
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")
        results = {}
        filters = {"project_id": "jnkns-jenkins"}
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
                    raise
        sheepdog.delete_nodes(nodes_dict, "main_account")

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
        sheepdog = Sheepdog()
        peregrine = Peregrine()
        # Create a node using sheepdog. Verify node is present.
        node = sheepdog.add_node(nodes.get_first_node(), "main_account")
        # Perform a query using an invalid project_id.
        filters = {"project_id": "NOT-EXIST"}
        response = peregrine.query_node_fields(node, filters)
        # Validate length of fields returned for node name is 0
        if len(response.json()["data"][node["name"]]) != 0:
            logger.error(
                "Found fields for {}. Response : {}".format(
                    node["name"], response.json()
                )
            )
            raise
        # Delete the node created. Verify node is deleted.
        sheepdog.delete_node(node, "main_account")

    @pytest.mark.peregrine
    def test_with_path_to_first_to_last_node(self):
        """
        Scenario: Test with_path_to - first to last node
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Query path from first node to last node.
            3. Verify first node name is present response.
            4. Delete all nodes. Verify all nodes are deleted.
        """
        sheepdog = Sheepdog()
        peregrine = Peregrine()
        # Create nodes using sheepdog. Verify nodes are present.
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")
        # Query path from first node to last node.
        response = peregrine.query_with_path_to(
            nodes.get_first_node(), nodes.get_last_node()
        )
        # Verify first node name is present response.
        try:
            if nodes.get_first_node()["name"] in response.json()["data"].keys():
                logger.info(response.json())
        except:
            logger.error(
                "{} not found in response {}".format(
                    nodes.get_first_node()["name"], response.json()
                )
            )
            raise
        # Delete all nodes. Verify all nodes are deleted.
        sheepdog.delete_nodes(nodes_dict, "main_account")

    @pytest.mark.peregrine
    def test_with_path_to_last_to_first_node(self):
        """
        Scenario: Test with_path_to - last to first node
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Query path from last node to first node.
            3. Verify last node name is present response.
            4. Delete all nodes. Verify all nodes are deleted.
        """
        sheepdog = Sheepdog()
        peregrine = Peregrine()
        # Create nodes using sheepdog. Verify nodes are present.
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")
        # Query path from last node to first node.
        response = peregrine.query_with_path_to(
            nodes.get_last_node(), nodes.get_first_node()
        )
        # Verify last node name is present response.
        try:
            if nodes.get_last_node()["name"] in response.json()["data"].keys():
                logger.info(response.json())
        except:
            logger.error(
                "{} not found in response {}".format(
                    nodes.get_last_node()["name"], response.json()
                )
            )
            raise
        # Delete all nodes. Verify all nodes are deleted.
        sheepdog.delete_nodes(nodes_dict, "main_account")

    @pytest.mark.skip("Test case is broken")
    def test_submit_data_node_with_consent_codes(self):
        """
        Scenario: Update file with invalid property
        Steps:
            1. Retrieve records from Indexd
            2. Delete all records retrieved.
            3. Submit metatdata for file node, including consent codes
            4. Verify indexd record was created with the correct consent codes
        """
        indexd = Indexd()
        sheepdog = Sheepdog()
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
        indexd.file_equals(response, file_node_wit_ccs)

    @pytest.mark.indexd
    def test_submit_and_delete_file(self):
        """
        Scenario: Submit and delete file
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Create a file node and retrieve record from indexd
            3. Delete file node and delete indexd record
            4. Delete all nodes. Verify all nodes are deleted.
        """
        sheepdog = Sheepdog()
        indexd = Indexd()
        # Adding all nodes except file node
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")

        # Adding file node and retrieveing indexd record
        node = sheepdog.add_node(nodes.get_file_node(), "main_account")
        record = indexd.get_record(indexd_guid=node["did"])
        rev = indexd.get_rev(record)

        # Deleting file node and indexd record
        sheepdog.delete_node(node, "main_account")
        delete_record = indexd.delete_record(guid=node["did"], rev=rev)
        assert delete_record == 200, f"Failed to delete record {node['did']}"

        # Delete all remaining records
        sheepdog.delete_nodes(nodes_dict, "main_account")

    @pytest.mark.indexd
    def test_submit_file_with_url(self):
        """
        Scenario: Submit file with URL
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Create a file node with URL and retrieve record from indexd
            3. Delete file node and delete indexd record
            4. Delete all nodes. Verify all nodes are deleted.
        """
        sheepdog = Sheepdog()
        indexd = Indexd()
        test_url = "s3://cdis-presigned-url-test/testdata"
        # Adding all nodes except file node
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")

        # Adding file node and retrieveing indexd record
        file_node = nodes.get_file_node()
        file_node["data"]["urls"] = test_url
        node = sheepdog.add_node(file_node, "main_account")
        record = indexd.get_record(indexd_guid=node["did"])
        rev = indexd.get_rev(record)

        # Deleting file node and indexd record
        sheepdog.delete_node(node, "main_account")
        delete_record = indexd.delete_record(guid=node["did"], rev=rev)
        assert delete_record == 200, f"Failed to delete record {node['did']}"

        # Delete all remaining records
        sheepdog.delete_nodes(nodes_dict, "main_account")

    @pytest.mark.indexd
    def test_submit_file_then_update_with_url(self):
        """
        Scenario: Submit file then update with URL
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Create a file node and retrieve record from indexd
            3. Add URL to file node and update file node.
            4. Delete file node and delete indexd record
            5. Delete all nodes. Verify all nodes are deleted.
        """
        sheepdog = Sheepdog()
        indexd = Indexd()
        test_url = "s3://cdis-presigned-url-test/testdata"
        # Adding all nodes except file node
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")

        # Adding file node and retrieveing indexd record without URL
        file_node = nodes.get_file_node()
        node = sheepdog.add_node(file_node, "main_account")
        record = indexd.get_record(indexd_guid=node["did"])
        rev = indexd.get_rev(record)

        # Add URL to the node data and update it
        file_node["data"]["urls"] = test_url
        node = sheepdog.update_node(file_node, "main_account")
        record = indexd.get_record(indexd_guid=node["did"])
        rev = indexd.get_rev(record)

        # Deleting file node and indexd record
        sheepdog.delete_node(node, "main_account")
        delete_record = indexd.delete_record(guid=node["did"], rev=rev)
        assert delete_record == 200, f"Failed to delete record {node['did']}"

        # Delete all remaining records
        sheepdog.delete_nodes(nodes_dict, "main_account")

    @pytest.mark.wip("This test case is broken due to bug in sheepdog")
    def test_submit_file_invalid_property(self):
        """
        Scenario: Submit file invalid property
        Steps:
            1. Create nodes using sheepdog. Verify nodes are present.
            2. Create a file node with an invalid property
            3. Validate node wasn't added
            4. Delete all nodes. Verify all nodes are deleted.
        """
        sheepdog = Sheepdog()

        # Adding all nodes except file node
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")

        # Adding invalid property to node and attempting to create record
        file_node = nodes.get_file_node()
        file_node["data"]["file_size"] = "hello"
        node = sheepdog.add_node(
            file_node, "main_account", validate_node=False, invalid_property=True
        )
        logger.info(node)

        # Need to insert check to validate "Internal server error. Sorry, something unexpected went wrong!" is part of transactional_errors

        # Delete all remaining records
        sheepdog.delete_nodes(nodes_dict, "main_account")

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
            6. Delete all nodes. Verify all nodes are deleted.
        """
        sheepdog = Sheepdog()
        indexd = Indexd()
        # Adding all nodes except file node
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")

        # Adding file node and retrieveing indexd record
        file_node = nodes.get_file_node()
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
        assert delete_record == 200, f"Failed to delete record {node['did']}"

        # Need to insert check to validate "Internal server error. Sorry, something unexpected went wrong!" is part of transactional_errors

        # Delete all remaining records
        sheepdog.delete_nodes(nodes_dict, "main_account")

    def test_core_metadata(self):
        """
        Scenario: Test core metadata
        Steps:
        """
        sheepdog = Sheepdog()
        coremetadata = CoreMetaData()
        # Create nodes using sheepdog. Verify nodes are present.
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")

        valid_file = sheepdog.add_node(nodes.get_file_node(), "main_account")
        metadata = coremetadata.get_core_metadata(file=valid_file, user="main_account")
        coremetadata.see_json_core_metadata(file=valid_file, metadata=metadata)

        metadata = coremetadata.get_core_metadata(
            file=valid_file, user="main_account", format="x-bibtex"
        )
        coremetadata.see_bibtex_core_metadata(file=valid_file, metadata=metadata)

        sheepdog.delete_node(valid_file, "main_account")

        # Delete all remaining records
        sheepdog.delete_nodes(nodes_dict, "main_account")

    def test_core_metadata_invalid_object_id(self):
        """
        Scenario: Test core metadata invalid object_id
        Steps:
        """
        sheepdog = Sheepdog()
        coremetadata = CoreMetaData()
        # Create nodes using sheepdog. Verify nodes are present.
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")

        invalid_file = nodes.get_file_node()
        invalid_file["data"]["object_id"] = "invalid_object_id"
        invalid_file["did"] = "invalid_object_id"
        metadata = coremetadata.get_core_metadata(
            file=invalid_file, user="main_account", expected_status=404
        )
        coremetadata.see_core_metadata_error(
            metadata=metadata, message='object_id "invalid_object_id" not found'
        )

        # Delete all remaining records
        sheepdog.delete_nodes(nodes_dict, "main_account")

    def test_core_metadata_no_permission(self):
        """
        Scenario: Test core metadata no permission
        Steps:
        """
        sheepdog = Sheepdog()
        coremetadata = CoreMetaData()
        # Create nodes using sheepdog. Verify nodes are present.
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")

        valid_file = sheepdog.add_node(nodes.get_file_node(), "main_account")
        metadata = coremetadata.get_core_metadata(
            file=valid_file,
            user="main_account",
            expected_status=401,
            invalid_authorization=True,
        )
        coremetadata.see_core_metadata_error(
            metadata=metadata,
            message="Authentication Error: could not parse authorization header",
        )

        sheepdog.delete_node(valid_file, "main_account")

        # Delete all remaining records
        sheepdog.delete_nodes(nodes_dict, "main_account")

    @pytest.mark.wip("Test in development")
    def test_core_metadata_page(self):
        """
        Scenario: Test core metadata page
        Steps:
        """
        sheepdog = Sheepdog()
        peregrine = Peregrine()
        # login_page = LoginPage()
        coremetadata = CoreMetaData()
        # Create nodes using sheepdog. Verify nodes are present.
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")

        valid_file = sheepdog.add_node(nodes.get_file_node(), "main_account")
        metadata = coremetadata.get_core_metadata(file=valid_file, user="main_account")
        coremetadata.see_json_core_metadata(file=valid_file, metadata=metadata)
        logger.info(metadata.json())

        # Perform login and logout operations using main_account to create a login record for audit service to access
        logger.info("Logging in with mainAcct")
        # login_page.go_to(page)
        # login_page.login(page)
        # login_page.logout(page)

        # sheepdog.delete_node(valid_file, "main_account")

        # Delete all remaining records
        # sheepdog.delete_nodes(nodes_dict, "main_account")
