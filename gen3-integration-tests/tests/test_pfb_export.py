import json
import os
from datetime import datetime

import fastavro
import pytest
import requests
import utils.gen3_admin_tasks as gat
from gen3.auth import Gen3Auth
from pages.exploration import ExplorationPage
from pages.login import LoginPage
from playwright.sync_api import Page
from services.graph import GraphDataTools
from utils import logger


def check_export_to_pfb_button(data):
    for button in data:
        if button.get("type") == "export-to-pfb":
            return True
    return False


def validate_json_for_export_to_pfb_button(data):
    if isinstance(data, dict):
        if "buttons" in data and check_export_to_pfb_button(data["buttons"]):
            return True
        return any(validate_json_for_export_to_pfb_button(val) for val in data.values())
    if isinstance(data, list):
        return any(validate_json_for_export_to_pfb_button(item) for item in data)
    return False


@pytest.mark.skipif(
    "portal" not in pytest.deployed_services,
    reason="portal service is not running on this environment",
)
@pytest.mark.skipif(
    not validate_json_for_export_to_pfb_button(gat.get_portal_config()),
    reason="Export to PFB button not present in gitops.json",
)
@pytest.mark.skipif(
    "sheepdog" not in pytest.deployed_services,
    reason="sheepdog service is not running on this environment",
)
@pytest.mark.skipif(
    "tube" not in pytest.deployed_services
    and os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE",
    reason="tube service is not running on this environment",
)
@pytest.mark.skipif(
    "pelican-export" not in pytest.enabled_sower_jobs,
    reason="pelican-export is not part of sower in manifest",
)
@pytest.mark.tube
@pytest.mark.pfb
@pytest.mark.guppy
@pytest.mark.portal
@pytest.mark.sower
class TestPFBExport(object):
    @classmethod
    def setup_class(cls):
        cls.auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        cls.sd_tools = GraphDataTools(
            auth=cls.auth, program_name="jnkns", project_code="jenkins2"
        )
        gat.clean_up_indices(test_env_namespace=pytest.namespace)
        logger.info("Submitting test records")
        cls.sd_tools.submit_all_test_records()
        gat.run_gen3_job("etl", test_env_namespace=pytest.namespace)
        if validate_json_for_export_to_pfb_button(gat.get_portal_config()):
            if os.getenv("REPO") == "cdis-manifest" or os.getenv("REPO") == "gitops-qa":
                # Guppy config is changed to use index names from etlMapping.yaml from the manifest's folder
                gat.mutate_manifest_for_guppy_test(
                    test_env_namespace=pytest.namespace, indexname="manifest"
                )

    @classmethod
    def teardown_class(cls):
        gat.clean_up_indices(test_env_namespace=pytest.namespace)
        cls.sd_tools.delete_all_records()
        if validate_json_for_export_to_pfb_button(gat.get_portal_config()):
            if os.getenv("REPO") == "cdis-manifest" or os.getenv("REPO") == "gitops-qa":
                gat.mutate_manifest_for_guppy_test(test_env_namespace=pytest.namespace)

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

        exploration_page.navigate_to_exploration_tab_with_pfb_export_button(page)
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
