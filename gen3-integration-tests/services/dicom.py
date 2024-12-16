import pytest
import requests
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission
from utils import TEST_DATA_PATH_OBJECT, logger


class Dicom(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}"
        self.DICOM_INSTANCES = "/dicom-server/instances"
        self.DICOM_STUDIES = "/dicom-server/studies"

    def submit_dicom_file(self, user="main_account", expected_status=200):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        access_token = auth.get_access_token()
        url = self.BASE_URL + self.DICOM_INSTANCES
        with (TEST_DATA_PATH_OBJECT / "dicom/test_file.dcm").open("rb") as file:
            content = file.read()
        headers = {
            "Content-Type": "application/dicom",
            "Authorization": f"bearer {access_token}",
        }
        response = requests.post(url=url, data=content, headers=headers)
        assert (
            response.status_code == expected_status
        ), f"Expected status {expected_status} but got {response.status_code}"
        if response.status_code == 200:
            logger.info(response.json())
            return response.json()

    def get_studies(self, study_instance, user="main_account"):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        url = self.DICOM_STUDIES + "/" + study_instance
        response = auth.curl(path=url)
        assert (
            response.status_code == 200
        ), f"Expected status 200 but got {response.status_code}"
        return response.json()

    def submit_dicom_data(
        self,
        case_submitted_id,
        program,
        project,
        study_id,
        dataset_submitter_id,
        case_linked_external_data,
        user="main_account",
    ):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        submit_data = {
            "type": "imaging_study",
            "datasets": {"submitter_id": dataset_submitter_id},
            "cases": [
                {
                    "submitter_id": case_submitted_id,
                }
            ],
            "image_data_modified": False,
            "submitter_id": study_id,
        }
        Gen3Submission(auth_provider=auth).submit_record(program, project, submit_data)

    def get_dicom_file(self, dicom_file_id, user="main_account", expected_status=200):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        url = self.DICOM_INSTANCES + "/" + dicom_file_id
        response = auth.curl(path=url)
        assert (
            response.status_code == expected_status
        ), f"Expected status {expected_status} but got {response.status_code}"
