import os
import pytest
import requests

from cdislogging import get_logger
from gen3.auth import Gen3Auth
from utils import TEST_DATA_PATH_OBJECT
import requests


logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Guppy(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}"
        self.API_GUPPY_ENDPOINT = "/guppy"

    def validate_guppy_status(self, user, expectedStatus):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        url = self.API_GUPPY_ENDPOINT + "/_status"
        response = auth.curl(path=url)
        logger.info("Guppy status code : " + str(response.status_code))
        assert expectedStatus == response.status_code
        data = response.json()
        assert "jenkins_subject_1" in data["indices"]
        assert "jenkins_file_1" in data["indices"]
        return True

    def validate_guppy_query(self, queryFile, responseFile, user, expectedStatus):
        queryFile = (TEST_DATA_PATH_OBJECT / "guppy_data" / queryFile).read_text(
            encoding="UTF-8"
        )
        responseFile = (TEST_DATA_PATH_OBJECT / "guppy_data" / responseFile).read_text(
            encoding="UTF-8"
        )
        queryToSubmit = "".join(queryFile.split("\n"))
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        url = self.API_GUPPY_ENDPOINT + "/graphql"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "bearer {}".format(auth.get_access_token()),
        }
        response = requests.post(
            url=self.BASE_URL + url, data=queryToSubmit, headers=headers
        )
        logger.info(f"Status code: {response.status_code}")
        assert expectedStatus == response.status_code
        # logger.info(eval(responseFile))
        logger.info(dict(response.json()))
        assert eval(responseFile) == dict(response.json())
        return True
