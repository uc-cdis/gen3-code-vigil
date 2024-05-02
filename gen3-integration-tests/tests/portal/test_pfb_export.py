import pytest
import os
import requests
import fastavro
import json

from datetime import datetime
from playwright.sync_api import Page, expect
from pages.login import LoginPage
from pages.exploration import ExplorationPage
from utils.test_execution import screenshot
import utils.gen3_admin_tasks as gat

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class TestPFBExport(object):
    # @classmethod
    # def setup_class(cls):
    #     # Generate test data in jenkins
    #     gat.generate_test_data(pytest.namespace, 10)
    #     # Run ELT job after generating test data
    #     gat.run_gen3_job(pytest.namespace, "etl")
    #     # Rolling guppy after the ETL job run
    #     gat.run_gen3_job(pytest.namespace, "kube-setup-guppy")

    def test_pfb_export(self, page):
        """
        Scenario: Test PFB Export
        Steps:
            1. Generate Data for jenkins env
            2. Run ETL job and roll Guppy service after the ETL is successful
            3. Login with main_account and go to Exploration Page
            4. Click on 'Export to PFB' button and check the footer for success message
            5. Get the PreSigned URl and make a API call to get the content of the PFB file
            6. Run PyPFB CLI command to
        """
        login_page = LoginPage()
        exploration_page = ExplorationPage()
        # Go to login page and log in with main_account user
        login_page.go_to(page)
        login_page.login(page)
        #
        exploration_page.go_to_and_check_button(page)
        download_pfb_link = exploration_page.check_pfb_status(page)
        logger.debug(f"Downloadable PFB File Link : {download_pfb_link}")
        # Sending API request to 'download_pfb_link' to get the content of the file
        pfb_download_file = requests.get(
            download_pfb_link, headers={"Accept": "binary/octet-stream"}
        )
        pfb_content = pfb_download_file.content
        logger.debug(f"PFB Content : {pfb_content}")

        unique_num = int(datetime.now().timestamp())
        logger.debug(f"{unique_num}")
        pfb_file_path = f"./test_export_{unique_num}.avro"

        # Writing content of the Avro file to local avro file
        with open(pfb_file_path, "wb") as pfb_file:
            pfb_file.write(pfb_content)

        if not os.path.exists(pfb_file_path):
            raise ValueError(f"A {pfb_file_path} file should have been created")

        # Print the content of pfb_file_path
        with open(pfb_file_path, "rb") as avro_file:
            pfb_content = avro_file.read()
            logger.debug(f"Contents of {pfb_file_path}: {pfb_content}")

        # Convert content of avro file to json file
        with open(pfb_file_path, "rb") as avro_file:
            avro_reader = fastavro.reader(avro_file)
            records = [record for record in avro_reader]

        # Convert Avro records to JSON format
        json_data = json.dumps(records, indent=2)

        # Write JSON data to file
        json_file_path = f"./test_export_{unique_num}.json"
        with open(json_file_path, "w") as json_file:
            json_file.write(json_data)

        node_list = []
        with open(json_file_path, "r") as json_file:
            json_content = json.load(json_file)
            for item in json_content:
                nodes = item.get("object", {}).get("nodes", [])
                for node in nodes:
                    node_name = node.get("name")
                    if node_name:
                        node_list.append(node_name)

        logger.debug(f"Node Names : {node_list}")
        assert "program" in node_list, "Program node not found in node list"
        assert "project" in node_list, "Project node not found in node list"
        if "anvil" in pytest.namespace:
            assert "subject" in node_list, "Subject node not found in node list"
        else:
            assert "study" in node_list, "Study node not found in node list"
