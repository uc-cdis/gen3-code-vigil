"""
Core Metadata Page
"""
import json
import os
import pytest
import requests

from cdislogging import get_logger
from pages.login import LoginPage
from pages.core_metadata_page import CoreMetadataPage
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
class TestCoreMetadataPage:
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
        sheepdog = Sheepdog()
        peregrine = Peregrine()
        login_page = LoginPage()
        core_metadata_page = CoreMetadataPage()
        coremetadata = CoreMetaData()
        # Create nodes using sheepdog. Verify nodes are present.
        nodes_dict = sheepdog.add_nodes(nodes.get_path_to_file(), "main_account")

        valid_file = sheepdog.add_node(nodes.get_file_node(), "main_account")
        metadata = coremetadata.get_core_metadata(file=valid_file, user="main_account")
        peregrine.see_json_core_metadata(file=valid_file, metadata=metadata)

        # Perform login and logout operations using main_account to create a login record for audit service to access
        logger.info("Logging in with mainAcct")
        login_page.go_to(page)
        login_page.login(page)
        core_metadata_page.goto_metadata_page(page, metadata.json()["object_id"])
        core_metadata_page.verify_metadata_page_elements(page)
        login_page.logout(page)

        sheepdog.delete_node(valid_file, "main_account")

        # Delete all remaining records
        sheepdog.delete_nodes(nodes_dict, "main_account")
