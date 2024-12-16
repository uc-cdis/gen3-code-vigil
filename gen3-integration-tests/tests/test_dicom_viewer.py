import pytest
import utils.gen3_admin_tasks as gat
from gen3.auth import Gen3Auth
from pages.dicom import DicomPage
from pages.login import LoginPage
from playwright.sync_api import Page
from services.dicom import Dicom
from services.graph import GraphDataTools
from utils import logger


@pytest.mark.skipif(
    "midrc" not in pytest.namespace, reason="DICOM test is specific to MIDRC"
)
@pytest.mark.dicom_viewer
@pytest.mark.sequential
class TestDicomViewer(object):
    auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
    sd_tools = GraphDataTools(auth=auth, program_name="DEV", project_code="DICOM_test")
    dicom = Dicom()
    dicom_page = DicomPage()
    login_page = LoginPage()
    file_id = ""
    study_id = ""

    @classmethod
    def setup_class(cls):
        cls.sd_tools.delete_all_records()
        file_res = cls.dicom.submit_dicom_file()
        cls.file_id = file_res["ID"]
        study_instance = file_res["ParentStudy"]
        study_res = cls.dicom.get_studies(study_instance=study_instance)
        cls.study_id = study_res["MainDicomTags"]["StudyInstanceUID"]
        cls.sd_tools.submit_all_test_records()
        logger.info("Running first etl")
        gat.run_gen3_job("etl", test_env_namespace=pytest.namespace)
        for key, item in cls.sd_tools.test_records.items():
            if key == "dataset":
                dataset_submitter_id = item.props["submitter_id"]
            if key == "case":
                case_linked_external_data = item.props["linked_external_data"]
                case_submitted_id = item.props["submitter_id"]
        cls.dicom.submit_dicom_data(
            program="DEV",
            project="DICOM_test",
            study_id=cls.study_id,
            dataset_submitter_id=dataset_submitter_id,
            case_submitted_id=case_submitted_id,
            case_linked_external_data=case_linked_external_data,
        )
        logger.info("Running second etl")
        gat.run_gen3_job("etl", test_env_namespace=pytest.namespace)

    @classmethod
    def teardown_class(cls):
        cls.sd_tools.delete_all_records()

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
