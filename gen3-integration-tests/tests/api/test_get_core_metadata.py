"""
Get Core Metadata
"""
import json
import os
import pytest
import requests

from cdislogging import get_logger
from services.coremetadata import CoreMetaData
from services.peregrine import Peregrine
from services.sheepdog import Sheepdog
from utils import nodes
from utils.gen3_admin_tasks import kube_setup_service
from utils.test_setup import create_program_project, generate_graph_data

from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from playwright.sync_api import Page

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.sheepdog
@pytest.mark.peregrine
class TestGetCoreMetadata:
    def setup_method(self, method):
        sdp = Sheepdog()
        # Delete all existing nodes prior to running the test cases
        logger.info("Deleting any existing nodes before test case execution")
        sdp.delete_all_nodes()

    def test_core_metadata(self):
        """
        Scenario: Test core metadata
        Steps:
        """
        sheepdog = Sheepdog()
        peregrine = Peregrine()
        coremetadata = CoreMetaData()
        # Create nodes using sheepdog. Verify nodes are present.
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")

        valid_file = sheepdog.add_node(nodes.get_file_node(), "main_account")
        metadata = coremetadata.get_core_metadata(file=valid_file, user="main_account")
        peregrine.see_json_core_metadata(file=valid_file, metadata=metadata)

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
