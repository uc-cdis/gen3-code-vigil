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

    def get_dicom_file(self, dicom_file_id, user="main_account", expected_status=200):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        url = self.DICOM_INSTANCES + "/" + dicom_file_id
        response = auth.curl(path=url)
        assert (
            response.status_code == expected_status
        ), f"Expected status {expected_status} but got {response.status_code}"
