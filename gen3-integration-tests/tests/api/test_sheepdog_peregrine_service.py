"""
SHEEPDOG & PEREGRINE SERVICE
"""
import os
import pytest

from cdislogging import get_logger

from utils import nodes
from services.sheepdog import Sheepdog
from services.peregrine import Peregrine

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.sheepdog
@pytest.mark.peregrine
class TestSheepdogPeregrineService:
    @classmethod
    def setup_class(cls):
        sdp = Sheepdog()
        # Delete all existing nodes prior to running the test cases
        sdp.deleteAllNodes()

    '''@classmethod
    def teardown_class(self):
        sdp = Sheepdog()
        # Delete all nodes post running the test cases
        sdp.deleteAllNodes()

    # SubmitAndQueryNodesTest.js
    def test_submit_and_delete_node(self):
        """
        Scenario: Submit and delete node
        Steps:
            1. Create a node using sheepdog. Verify node is present.
            2. Delete the node created. Verify node is deleted.
        """
        sheepdog = Sheepdog()
        node = sheepdog.addNode(nodes.ithNodeInPath(1), "main_account")
        sheepdog.deleteNode(node, 'main_account')

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
        node = sheepdog.addNode(nodes.ithNodeInPath(1), "main_account")
        queryToSubmit = "query Test { alias1: " + node['data']['type'] + " { id } }"
        response = peregrine.query(queryToSubmit, {}, 'main_account')
        data = response.json()['data']
        if 'alias1' not in data or len(data['alias1']) != 1:
            logger.error("Either alias1 is missing or exactly 1 id wasn\'t found. Response: {}".format(data))
            raise
        sheepdog.deleteNode(node, 'main_account')

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
        parentNode = nodes.ithNodeInPath(1)
        parentResponse = peregrine.queryNodeFields(parentNode)
        if len(parentResponse.json()['data'][parentNode['name']]) != 0:
            logger.error('Found fields for {}. Response : {}'.format(parentNode['name'], parentResponse.json()))
            raise

        # Attempt to add second node
        secondNode = sheepdog.addNode(nodes.ithNodeInPath(2), "main_account", validate_node=False)
        if len(secondNode.json()['data']['addRes']['code']) != 400:
            logger.error('Found status which was not 400. Response : {}'.format(secondNode.json()))
            raise

    def test_query_on_invalid_field(self):
        """
        Scenario: Query on invalid field
        Steps:
            1. Get type field value from First node
            2. Perform a simple query using an invalid field
        """
        peregrine = Peregrine()
        invalidField = 'abcdef'
        nodeType = nodes.ithNodeInPath(1)['data']['type']
        queryToSubmit = "{ " + nodeType + "{ " + invalidField + "}}"
        response = peregrine.query(queryToSubmit, {}, 'main_account').json()
        if 'Cannot query field "{}" on type "{}".'.format(invalidField, nodeType) != response['errors'][0]:
            logger.error('Cannot query field "{}" on type "{}". entry wasn\'t found. Response : {}'.format(invalidField, nodeType, response))
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
        sheepdog = Sheepdog()
        peregrine = Peregrine()
        node = sheepdog.addNode(nodes.ithNodeInPath(1), "main_account")
        filters = {'project_id': 'NOT-EXIST'}
        response = peregrine.queryNodeFields(node, filters)
        if len(response.json()['data'][node['name']]) != 0:
            logger.error('Found fields for {}. Response : {}'.format(node['name'], response.json()))
            raise
        sheepdog.deleteNode(node, 'main_account')'''

    def test_submit_and_delete_node_path(self):
        """
        Scenario: Submit and delete node path
        Steps:
        """
        sheepdog = Sheepdog()
