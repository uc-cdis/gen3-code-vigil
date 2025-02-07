import pytest
import requests
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission
from utils import TEST_DATA_PATH_OBJECT, logger


class Dicom(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}"
        self.DICOM_INSTANCES = "/orthanc/instances"
        self.DICOM_STUDIES = "/orthanc/studies"

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

    def get_dicom_file(self, dicom_file_id, user="main_account", expected_status=200):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        url = self.DICOM_INSTANCES + "/" + dicom_file_id
        response = auth.curl(path=url)
        assert (
            response.status_code == expected_status
        ), f"Expected status {expected_status} but got {response.status_code}"
