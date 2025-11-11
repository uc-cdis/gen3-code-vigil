import json
import os
import re
import time

import pytest
import requests
from playwright.sync_api import Page, expect
from requests.exceptions import ConnectionError, RequestException, Timeout
from utils import TEST_DATA_PATH_OBJECT, logger
from utils.test_execution import screenshot


# TODO : enable this test after the manifest PRs are ready to roll
@pytest.mark.wip
@pytest.mark.skipif(
    "portal" not in pytest.deployed_services
    and "frontend-framework" not in pytest.deployed_services,
    reason="Both portal and frontend-framework services are not running on this environment",
)
class TestDataGuids(object):
    @classmethod
    def setup_class(cls):
        cls.variables = {}
        # dataguids_url = "https://dataguids.org"
        cls.dataguids_url = f"{pytest.root_url_portal}"
        cls.non_existent_guids = [
            "dg.ABCD/0000b4b4-2af4-42e2-9bfa-6fd11e5fb97a",
            "0000b456-3r56-1dr3-0rt4-6fd11e5fb97a",
        ]
        cls.variables["guids"] = []
        logger.info("Getting all the hosts from manifest.json ...")
        try:
            manifest_json = json.loads(
                (TEST_DATA_PATH_OBJECT / "configuration/manifest.json").read_text()
            )
        except FileNotFoundError:
            logger.error("manifest.json not found")
            raise
        nested_json_str = manifest_json.get("data", {}).get("json")
        if nested_json_str:
            nested_json = json.loads(nested_json_str)
            indexd_dist = nested_json.get("indexd", {}).get("dist", [])
            host_list = [entry.get("host") for entry in indexd_dist]
            logger.debug(f"Host_List: {host_list}")

            logger.info("Getting the first guid fom hosts ...")
            for host in host_list:
                try:
                    record = requests.get(f"{host}index?limit=1")
                    record_data_json = record.json()
                    logger.debug(f"Record_Data : {record_data_json}")
                    if "records" in record_data_json and record_data_json["records"]:
                        guid = record_data_json["records"][0]["did"]
                        cls.variables["guids"].append(guid)
                        logger.debug(f"GUID from {host}: {guid}")
                    else:
                        logger.error(
                            f"No 'records' or empty 'records' key found in response from {host}"
                        )
                except requests.exceptions.RequestException as e:
                    logger.error(f"Request to {host} failed : {e}")
        else:
            logger.error("No 'json' block found in manifest data")

    def test_resolve_prefixes(self, page: Page):
        """
        Scenario: Resolve GUIDS with different prefixes and without prefix
        Steps:
            1. Check if on Dataguids.org homepage
            2. From the list of guids, resolve the guids
            3. And check if the result shows up
        """
        for correct_guid in self.variables["guids"]:
            logger.info(f"Resolving GUID {correct_guid} ...")
            page.goto(self.dataguids_url)
            screenshot(page, "DataGUIDPageValidGUID")
            page.locator("//input[@id='guidval']").fill(correct_guid)
            resolve_button = page.locator("//button[@id='resolveit']")
            resolve_button.scroll_into_view_if_needed()
            resolve_button.click()
            time.sleep(5)
            resolve_result = page.locator("//pre[@id='resolverresult']")
            resolve_result.wait_for()
            screenshot(page, "ResolvedGUID")
            resolved_text = resolve_result.text_content()
            resolved_json = json.loads(resolved_text)
            resolved_id = resolved_json["data_object"]["id"]
            assert (
                resolved_id == correct_guid
            ), f"Expected ID {correct_guid}, but got {resolved_id}"

    def test_drs_endpoint_and_resolve_guid(self, page: Page):
        """
        Scenario: Test if the DRS endpoint resolves GUID
        Steps:
            1. Go to /ga4gh/dos/v1/dataobjects/ endpoint with the guid
            2. And check if the result shows up
        """
        for correct_guid in self.variables["guids"]:
            try:
                page.goto(
                    f"{self.dataguids_url}/ga4gh/dos/v1/dataobjects/{correct_guid}"
                )
                id_content = page.content()
                logger.debug(f"Response content: {id_content}")
                match = re.search(r"<pre>(.*?)</pre>", id_content, re.DOTALL)
                if match:
                    json_text = match.group(1).strip()  # Extracted JSON text
                else:
                    logger.error("Failed to find JSON in response")
                    assert False, "JSON part not found in response"
                try:
                    json_data = json.loads(json_text)
                    logger.debug(f"GA4GH request response : {json_data}")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON: {e}")
                    assert False, "Response is not valid JSON response"
                guid = json_data.get("data_object", {}).get("id")
                assert (
                    guid == correct_guid
                ), f"GUID {correct_guid} not found in response"
            except (RequestException, ConnectionError, Timeout) as e:
                logger.error(f"Request failed: {e}")
                assert False, f"Request to {self.dataguids_url} failed: {e}"

    def test_nonexistent_guid(self, page: Page):
        """
        Scenario: Resolve GUIDS with nonexistent guids
        Steps:
            1. Check if on Dataguids.org homepage
            2. From the list of nonexistent guids list, resolve the guids
            3. And check if the result shows up - 404 not found
        """
        for guid in self.non_existent_guids:
            logger.info(f"Resolving GUID {guid} ...")
            page.goto(self.dataguids_url)
            screenshot(page, "DataGUIDPageValidGUID")
            page.locator("//input[@id='guidval']").fill(guid)
            resolve_button = page.locator("//button[@id='resolveit']")
            resolve_button.scroll_into_view_if_needed()
            resolve_button.click()
            time.sleep(5)
            resolve_result = page.locator("//pre[@id='resolverresult']")
            resolve_result.wait_for()
            screenshot(page, "ResolvedGUID")
            resolved_text = resolve_result.text_content()
            logger.debug(f"Resolved Text : {resolved_text}")
            assert (
                resolved_text == f'Data GUID "{guid}" not found.'
            ), f'Expected "Data GUID \\"{guid}\\" not found." but got "{resolved_text}"'

    def test_drs_nonexistent_guid(self, page: Page):
        """
        Scenario: Test if the DRS endpoint resolves GUID
        Steps:
            1. Go to /ga4gh/dos/v1/dataobjects/ endpoint with the nonexistent guid
            2. And check if the result shows up - 404 not found
        """
        for guid in self.non_existent_guids:
            page.goto(f"{self.dataguids_url}/ga4gh/dos/v1/dataobjects/{guid}")
            id_content = page.content()
            logger.debug(f"Response content: {id_content}")
            match = re.search(r"<pre>(.*?)</pre>", id_content, re.DOTALL)
            if match:
                json_text = match.group(1).strip()  # Extracted JSON text
            else:
                logger.error("Failed to find JSON in response")
                assert False, "JSON part not found in response"
            try:
                json_data = json.loads(json_text)
                logger.debug(f"JSON Data: {json_data}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON: {e}")
                assert False, "Response is not valid JSON response"
            msg = json_data.get("msg")
            logger.debug(f" no record found: {msg}")
            assert msg == "no record found", f"GUID {guid} was found"
