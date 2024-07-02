import os
import pytest
import requests
import json

from utils import logger, TEST_DATA_PATH_OBJECT
from playwright.sync_api import expect
import utils.gen3_admin_tasks as gat


# TODO : enable this test after the manifest PRs are ready to roll
@pytest.mark.wip
class TestDataGuids:
    variables = {}
    dataguids_url = "https://dataguids.org"
    non_existent_guids = [
        "dg.ABCD/0000b4b4-2af4-42e2-9bfa-6fd11e5fb97a",
        "0000b456-3r56-1dr3-0rt4-6fd11e5fb97a",
    ]

    @classmethod
    def setup_class(cls):
        cls.variables["guids"] = []
        logger.info("Getting all the hosts from manifest.json ...")
        host_list_path = TEST_DATA_PATH_OBJECT / "dataguids" / "host_list.txt"
        logger.info("Getting the first guid fom hosts ...")
        with open(host_list_path, "r") as list:
            for host in list:
                record = requests.get(f"{host}index?limit=1")
                record_data_json = record.json()
                assert record_data_json, "Response is empty"
                guid = record_data_json["did"]
                cls.variables["guids"].append(guid)
                logger.debug(f"GUID from {host}: {guid}")

    def test_resolve_prefixes(self, page):
        """
        Scenario: Resolve GUIDS with different prefixes and without prefix
        Steps:
            1. Check if on Dataguids.org homepage
            2. From the list of guids, resolve the guids
            3. And check if the result shows up
        """
        for correct_guid in self.variables["guids"]:
            page.goto(self.dataguids_url)
            page.get_by_role("#guidval").fill(correct_guid)
            resolve_button = page.locator("#resolveit")
            resolve_button.scroll_into_view_if_needed()
            resolve_button.click()
            resolve_result = page.locator("#resolverresult")
            resolve_result.wait_for()
            expect(resolve_result).to_have_text(f'"id": "{correct_guid}"')

    def test_drs_endpoint_and_resolve_guid(self, page):
        """
        Scenario: Test if the DRS endpoint resolves GUID
        Steps:
            1. Go to /ga4gh/dos/v1/dataobjects/ endpoint with the guid
            2. And check if the result shows up
        """
        for correct_guid in self.variables["guids"]:
            page.goto(f"{self.dataguids_url}/ga4gh/dos/v1/dataobjects/{correct_guid}")
            id_content = page.content()
            expect(id_content).to_have_text(f'"id": "{correct_guid}"')

    def test_nonexistent_guid(self, page):
        """
        Scenario: Resolve GUIDS with nonexistent guids
        Steps:
            1. Check if on Dataguids.org homepage
            2. From the list of nonexistent guids list, resolve the guids
            3. And check if the result shows up - 404 not found
        """
        for guid in self.non_existent_guids:
            page.goto(self.dataguids_url)
            page.get_by_role("#guidval").fill(guid)
            resolve_button = page.locator("#resolveit")
            resolve_button.scroll_into_view_if_needed()
            resolve_button.click()
            resolve_result = page.locator("#resolverresult")
            resolve_result.wait_for()
            expect(resolve_result).to_have_text(f'Data GUID "{guid}" not found.')

    def test_drs_nonexistent_guid(self, page):
        """
        Scenario: Test if the DRS endpoint resolves GUID
        Steps:
            1. Go to /ga4gh/dos/v1/dataobjects/ endpoint with the nonexistent guid
            2. And check if the result shows up - 404 not found
        """
        for guid in self.non_existent_guids:
            page.goto(f"{self.dataguids_url}/ga4gh/dos/v1/dataobjects/{guid}")
            id_content = page.content()
            expect(id_content).to_have_text(f'Data GUID "{guid}" not found.')
