import pytest
import requests
import os
import utils.gen3_admin_tasks as gat
from utils import logger

from pages.login import LoginPage
from pages.indexing_page import IndexingPage
from services.indexd import Indexd


@pytest.mark.portal
@pytest.mark.sower
@pytest.mark.ssjdispatcher
class TestIndexingPage:
    test_guid = "c2da639f-aa25-4c4d-8e89-02a143788268"
    test_hash = "73d643ec3f4beb9020eef0beed440ad4"  # pragma: allowlist secret
    expected_result = (
        f"{test_guid},s3://cdis-presigned-url-test/testdata,,jenkins2,{test_hash},13,"
    )

    def teardown_class(cls):
        # Delete the indexd record after the test
        indexd = Indexd()
        delete_record = indexd.delete_record(cls.test_guid)
        assert delete_record == 200, f"Failed to delete record {cls.test_guid}"

    def test_indexing_upload_valid_manifest(self, page):
        """
        Scenario: Login and navigate to indexing page and upload dummy manifest
        Steps:
            1. Login with indexing_account user
            2. Navigate to indexing page
            3. Upload valid manifest and wait for manifest-indexing sower job to finish
            4. Check if the indexd record exists
            5. Check if the indexd record hashes exists
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
        indexing_page.upload_valid_indexing_manifest(page)
        # Check if the sowerjob pod for manifest-indexing has completed
        gat.check_kube_pods(pytest.namespace, "manifest-indexing", "sowerjob")
        # Get the indexd record and check if the hash value matches to the test_hash value
        index_record = indexd.get_record(self.test_guid)
        indexd_record_hash = index_record["hashes"]["md5"]
        logger.info(indexd_record_hash)
        assert (
            indexd_record_hash == self.test_hash
        ), f"Expected MD5 hash {self.test_hash}, but got {indexd_record_hash}"

    def test_indexing_download(self, page):
        """
        Scenario: Login and navigate to indexing page and download indexd manifest
        Steps:
            1. Login with indexing_account user
            2. Navigate to indexing page
            3. Click on Download and wait for manifest-indexing sower job to finish
            4. Send the request to the download url received from step 3
            5. Verify the downloaded data
        """
        login_page = LoginPage()
        indexing_page = IndexingPage()
        # Go to login page and login with indexing_account user
        login_page.go_to(page)
        login_page.login(page, user="indexing_account")
        # Go to indexing page and validate page is loaded
        indexing_page.go_to(page)
        manifest_link = indexing_page.download_manifest(page)
        logger.debug(f"Download Link : {manifest_link}")
        gat.check_kube_pods(pytest.namespace, "indexd-manifest", "sowerjob")
        # sending request with manifest_link to get manifest data
        manifest_link_resp = requests.get(manifest_link)
        logger.debug(manifest_link_resp.text)
        manifest_data = manifest_link_resp.text
        assert (
            self.expected_result in manifest_data
        ), "Expected result not found in downloaded manifest"

    def test_indexing_upload_invalid_manifest(self, page):
        """
        Scenario:
        Steps:
            1. Login with indexing_account user
            2. Navigate to indexing page
            3. Upload invalid manifest and wait for manifest-indexing sower job to finish
            4. Verify that upload has failed
        """
        login_page = LoginPage()
        indexing_page = IndexingPage()
        # Go to login page and login with indexing_account user
        login_page.go_to(page)
        login_page.login(page, user="indexing_account")
        # Go to indexing page and validate page is loaded
        indexing_page.go_to(page)
        # Upload the valid manifest via indexing page
        indexing_page.upload_invalid_indexing_manifest(page)
        # Check if the sowerjob pod for manifest-indexing has completed
        gat.check_kube_pods(pytest.namespace, "manifest-indexing", "sowerjob", True)
