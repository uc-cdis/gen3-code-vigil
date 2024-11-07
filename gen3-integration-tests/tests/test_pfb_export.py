import json
import os
from datetime import datetime

import fastavro
import pytest
import requests
from pages.exploration import ExplorationPage
from pages.login import LoginPage
from playwright.sync_api import Page
from utils import logger


@pytest.mark.pfb
@pytest.mark.portal
@pytest.mark.admin_vm_only
class TestPFBExport(object):
    def test_pfb_export(self, page: Page):
        """
        Scenario: Test PFB Export
        Steps:
            1. Login with main_account user
            2. Go to exploration page and check if 'Export to PFB' button is present
            3. Click on 'Export to PFB' button and check if job footer comes up
            4. Wait for sower job to finish - (can use check-kube-pod jenkins job)
            5. Send request to PFB link and save the content to avro file to local avro file
            6. Verify the node names from local avro file
        """
        login_page = LoginPage()
        exploration_page = ExplorationPage()
        # Go to login page and log in with main_account user
        login_page.go_to(page)
        login_page.login(page)

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
            logger.info(f"Contents of {pfb_file_path}: {pfb_content}")

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
        assert "subject" in node_list, "Subject node not found in node list"
