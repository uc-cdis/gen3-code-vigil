import json

import pytest
import utils.gen3_admin_tasks as gat
from gen3.auth import Gen3Auth
from pages.dicom import DicomPage
from pages.login import LoginPage
from playwright.sync_api import Page
from services.dicom import Dicom
from utils import TEST_DATA_PATH_OBJECT, logger
from utils.gen3_admin_tasks import check_ohif_viewer_service


@pytest.mark.skipif(
    "orthanc"
    not in json.loads(
        (TEST_DATA_PATH_OBJECT / "configuration" / "manifest.json").read_text()
    )["versions"].keys(),
    reason="DICOM service is not running on this environment",
)
@pytest.mark.skipif(
    "ohif-viewer"
    not in json.loads(
        (TEST_DATA_PATH_OBJECT / "configuration" / "manifest.json").read_text()
    )["versions"].keys(),
    reason="OHIF service is not running on this environment",
)
@pytest.mark.dicom_viewer
class TestDicomViewer(object):
    auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
    dicom = Dicom()
    dicom_page = DicomPage()
    login_page = LoginPage()
    file_id = "537a3dfd-229a25e0-8443a6b7-f1f512a6-8341ff24"
    study_id = "1.3.6.1.4.1.14519.5.2.1.113283142818507428913223457507116949429"

    @classmethod
    def setup_class(cls):
        check_ohif_viewer_service(pytest.namespace)

    def test_check_uploaded_dicom_file(self, page: Page):
        """
        Scenario: Verify Uploaded Dicom file
        Steps:
            1. Goto Exploration page and click on Imaging Studies tab
            2. Find the xref containing the study id
            3. Click on the button of the href
            4. Verify OHIF viewer page is launched for the study id
        """
        val = json.loads(
            (TEST_DATA_PATH_OBJECT / "configuration" / "manifest.json").read_text()
        )["versions"].keys()
        logger.info(val)
        if "ohif-viewer" in val:
            logger.info("ohif-viewer is present")
        # Login with main_account
        self.login_page.go_to(page)
        self.login_page.login(page, user="main_account")

        # Goto explorer page
        self.dicom_page.goto_explorer_page(page=page, study_id=self.study_id)

    def test_unauthorized_user_cannot_get_dicom_file(self):
        """
        Scenario: Unauthorized user cannot get dicom file
        Steps:
             1. Get dicom file deatils using dummy_one user
             2. Expect 403 in response, since dummy_one user doesn't have permission to get dicom file
        """
        self.dicom.get_dicom_file(
            dicom_file_id=self.file_id, user="dummy_one", expected_status=403
        )

    def test_unauthorized_user_cannot_get_non_exist_dicom_file(self):
        """
        Scenario: Unauthorized user cannot get non-exist dicom file
        Steps:
             1. Get non-exist dicom file deatils using dummy_one user
             2. Expect 404 in response, since the dicom file doesn't exists
        """
        non_exist_id = "538a3dfd-219a25e0-8443a0b7-d1f512a6-2348ff25"
        self.dicom.get_dicom_file(dicom_file_id=non_exist_id, expected_status=404)
