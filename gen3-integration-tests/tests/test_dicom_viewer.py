import json

import pytest
from gen3.auth import Gen3Auth
from pages.dicom import DicomPage
from pages.login import LoginPage
from playwright.sync_api import Page
from services.dicom import Dicom
from utils import TEST_DATA_PATH_OBJECT

"""
NOTE: To setup the index data for image study follow setup under
      (TEST_DATA_PATH_OBJECT / "test_setup" / "dicom_viewer_es") folder.
"""


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
    file_id = ""
    study_id = ""

    @classmethod
    def setup_class(cls):
        file_res = cls.dicom.submit_dicom_file()
        cls.file_id = file_res["ID"]
        study_instance = file_res["ParentStudy"]
        study_res = cls.dicom.get_studies(study_instance=study_instance)
        cls.study_id = study_res["MainDicomTags"]["StudyInstanceUID"]

    def test_check_uploaded_dicom_file(self, page: Page):
        """
        Scenario: Verify Uploaded Dicom file
        Steps:
            1. Goto Exploration page and click on Imaging Studies tab
            2. Find the xref containing the study id
            3. Click on the button of the href
            4. Verify OHIF viewer page is launched for the study id
        """
        # Login with main_account
        self.login_page.go_to(page)
        self.login_page.login(page, user="main_account")

        # Goto explorer page
        self.dicom_page.goto_explorer_page(page=page, study_id=self.study_id)

    def test_unauthorized_user_cannot_post_dicom_file(self):
        """
        Scenario: Unauthorized user cannot submit dicom file
        Steps:
            1. Submit a dicom file using dummy_one user
            2. Expect 403 in response, since dummy_one user doesn't have permission to submit dicom file
        """
        self.dicom.submit_dicom_file(user="dummy_one", expected_status=403)

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
