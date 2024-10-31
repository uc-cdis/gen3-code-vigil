import csv
import os
from uuid import uuid4

import pytest
import requests
import utils.gen3_admin_tasks as gat
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from pages.indexing_page import IndexingPage
from pages.login import LoginPage
from services.indexd import Indexd
from utils import TEST_DATA_PATH_OBJECT, logger


@pytest.mark.portal
@pytest.mark.sower
@pytest.mark.ssjdispatcher
@pytest.mark.admin_vm_only
class TestIndexingPage:
    variables = {}

    def setup_class(cls):
        cls.variables["test_guid"] = str(uuid4())
        cls.variables["md5sum"] = "73d643ec3f4beb9020eef0beed440ad4"
        cls.variables["expected_result"] = (
            f"{cls.variables['test_guid']},"
            "s3://cdis-presigned-url-test/testdata,,jenkins2,"
            f"{cls.variables['md5sum']},13,"
        )
        # Updating the manifests with test_guid
        valid_manifest_path = (
            TEST_DATA_PATH_OBJECT / "indexing_page" / "valid_test_manifest.tsv"
        )
        invalid_manifest_path = (
            TEST_DATA_PATH_OBJECT / "indexing_page" / "invalid_test_manifest.tsv"
        )
        cls.variables["valid_output_path"] = "valid_output.tsv"
        cls.variables["invalid_output_path"] = "invalid_output.tsv"
        # for valid_test_manifest
        tsv_column = "GUID"
        with open(valid_manifest_path, "r", newline="", encoding="utf-8") as input_file:
            reader = csv.DictReader(input_file, delimiter="\t")
            fieldnames = [tsv_column] + reader.fieldnames
            with open(
                cls.variables["valid_output_path"], "w", newline="", encoding="utf-8"
            ) as output_file:
                writer = csv.DictWriter(
                    output_file, fieldnames=fieldnames, delimiter="\t"
                )
                writer.writeheader()
                for row in reader:
                    row[tsv_column] = cls.variables["test_guid"]
                    writer.writerow(row)
        # for invalid_test_manifest
        invalid_tsv_column = "\ufeffGUID"
        with open(
            invalid_manifest_path, "r", newline="", encoding="utf-8"
        ) as input_file:
            reader = csv.DictReader(input_file, delimiter="\t")
            fieldnames = [invalid_tsv_column] + reader.fieldnames
            with open(
                cls.variables["invalid_output_path"], "w", newline="", encoding="utf-8"
            ) as output_file:
                writer = csv.DictWriter(
                    output_file, fieldnames=fieldnames, delimiter="\t"
                )
                writer.writeheader()
                for row in reader:
                    row[invalid_tsv_column] = str(uuid4())
                    writer.writerow(row)

    def teardown_class(cls):
        # Delete the indexd record after the test
        user = "indexing_account"
        auth = Gen3Auth(refresh_token=pytest.api_keys[user])
        indexd = Gen3Index(auth_provider=auth)
        try:
            indexd.delete_record(guid=cls.variables["test_guid"])
        except Exception as e:
            logger.exception(
                msg=f"Failed to delete record for guid {cls.test_guid}: {e}"
            )
        # Deleting output files after the test is done
        for file_path in [
            cls.variables["valid_output_path"],
            cls.variables["invalid_output_path"],
        ]:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted output file: {file_path}")
            else:
                logger.info(
                    f"Output file '{file_path}' not found, so no deletion needed"
                )

    def test_indexing_upload_and_download_valid_manifest(self, page):
        """
        Scenario: Login and navigate to indexing page and upload dummy manifest
        Steps:
            1. Login with indexing_account user
            2. Navigate to indexing page
            3. Upload valid manifest and wait for manifest-indexing sower job to finish
            4. Check if the indexd record exists
            5. Assert if the indexd record hashes matches
            6. Navigate to indexing page and click on 'Download Manifest' button
            7. Send the request to the download url received from step 3
            8. Verify the downloaded data
        """
        login_page = LoginPage()
        indexing_page = IndexingPage()
        indexd = Indexd()
        # Go to login page and login with indexing_account user
        login_page.go_to(page)
        login_page.login(page, user="indexing_account")
        # Go to indexing page and validate page is loaded
        indexing_page.go_to(page)
        # Upload the valid manifest via indexing page
        indexing_page.upload_valid_indexing_manifest(
            page, self.variables["valid_output_path"]
        )
        # Check if the sowerjob pod for manifest-indexing has completed
        gat.check_job_pod(
            "manifest-indexing", "sowerjob", test_env_namespace=pytest.namespace
        )
        # Get the indexd record and check if the hash value matches to the test_hash value
        index_record = indexd.get_record(self.variables["test_guid"])
        indexd_record_hash = index_record["hashes"]["md5"]
        logger.debug(f"Indexd record md5sum : {indexd_record_hash}")
        assert (
            indexd_record_hash == self.variables["md5sum"]
        ), f"Expected MD5 hash {self.variables['md5sum']}, but got {indexd_record_hash}"
        # Go to indexing page after uploading the valid manifest to perform download manifest
        indexing_page.go_to(page)
        # Click on 'Download Manifest' button and wait to get the manifest link
        manifest_link = indexing_page.get_manifest_download_link(page)
        logger.debug(f"Download Link : {manifest_link}")
        gat.check_job_pod(
            "indexd-manifest", "sowerjob", test_env_namespace=pytest.namespace
        )
        # Sending request with manifest_link to get manifest data
        manifest_link_resp = requests.get(manifest_link)
        logger.debug(f"Text from manifest link response : {manifest_link_resp.text}")
        manifest_data = manifest_link_resp.text
        # Verify downloaded data if it consists the uploaded manifest record
        assert (
            self.variables["expected_result"] in manifest_data
        ), "Expected result not found in downloaded manifest"

    def test_indexing_upload_invalid_manifest(self, page):
        """
        Scenario:
        Steps:
            1. Login with indexing_account user
            2. Navigate to indexing page
            3. Upload invalid manifest and wait for manifest-indexing sower job to finish
            4. Verify that upload has failed

        Invalid Manifest - '\ufeff' at the beginning of your file content indicates a Byte-Order Mark,
        is often used in text files to signal the encoding it can cause issues when parsing TSV.
        Also, there is a newline sequence '\n' within the value for testGUID, and an extra comma
        ',' at the end of the size value which can make the TSV content invalid or improperly formatted.
        """
        login_page = LoginPage()
        indexing_page = IndexingPage()
        # Go to login page and login with indexing_account user
        login_page.go_to(page)
        login_page.login(page, user="indexing_account")
        # Go to indexing page and validate page is loaded
        indexing_page.go_to(page)
        # Upload the valid manifest via indexing page
        indexing_page.upload_invalid_indexing_manifest(
            page, self.variables["invalid_output_path"]
        )
        # Check status of the sowerjob manifest-indexin pod , we expect the pods to fail as the manifest is invalid
        gat.check_job_pod(
            "manifest-indexing",
            "sowerjob",
            test_env_namespace=pytest.namespace,
            expect_failure=True,
        )
