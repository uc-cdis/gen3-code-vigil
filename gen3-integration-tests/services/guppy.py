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

    def validate_guppy_query(
        self,
        queryFile,
        responseFile,
        queryType,
        user,
        expectedStatus,
        endpoint="/graphql",
    ):
        queryFile = (
            TEST_DATA_PATH_OBJECT / "guppy_data" / "testData" / queryFile
        ).read_text(encoding="UTF-8")
        responseFile = (
            TEST_DATA_PATH_OBJECT / "guppy_data" / "testData" / responseFile
        ).read_text(encoding="UTF-8")
        queryToSubmit = "".join(queryFile.split("\n"))
        logger.info(queryToSubmit)
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)
        url = self.API_GUPPY_ENDPOINT + endpoint
        headers = {
            "Content-Type": "application/json",
            "Authorization": "bearer {}".format(auth.get_access_token()),
        }
        response = requests.post(
            url=self.BASE_URL + url, data=queryToSubmit, headers=headers
        )
        logger.info(f"Status code: {response.status_code}")
        assert expectedStatus == response.status_code
        if queryType == "mapping":
            assert self.match_mapping(dict(response.json()), eval(responseFile))
        elif queryType == "aggregation":
            assert self.match_aggregation(dict(response.json()), eval(responseFile))
        elif queryType == "histogram":
            assert self.match_histogram(dict(response.json()), eval(responseFile))
        elif queryType == "download":
            assert self.match_data_query(list(response.json()), eval(responseFile))
        else:
            actualResponse = dict(response.json())["data"]["subject"]
            expectedResponse = eval(responseFile)["data"]["subject"]
            assert self.match_data_query(actualResponse, expectedResponse)
        return True

    def match_mapping(self, actualResponse, expectedResponse):
        actualResponse = actualResponse["data"]
        expectedResponse = expectedResponse["data"]
        if "_mapping" not in actualResponse.keys():
            logger.error("_mapping is missing from response data")
        if "subject" not in actualResponse["_mapping"].keys():
            logger.error("subject is missing from response data")
        for key in expectedResponse["_mapping"]["subject"]:
            if key not in actualResponse["_mapping"]["subject"]:
                logger.error("{} is missing from response data".format(key))
        return True

    def match_aggregation(self, actualResponse, expectedResponse):
        actualResponse = actualResponse["data"]
        expectedResponse = expectedResponse["data"]
        if "_aggregation" not in actualResponse.keys():
            logger.error("_aggregation is missing from response data")
        if "subject" not in actualResponse["_aggregation"].keys():
            logger.error("subject is missing from response data")
        for key, val in expectedResponse["_aggregation"]["subject"].items():
            if key not in actualResponse["_aggregation"]["subject"]:
                logger.error("{} is missing from response data".format(key))
            if not val == actualResponse["_aggregation"]["subject"][key]:
                logger.error(
                    "{} mismatch between expected and response data".format(val)
                )
        return True

    def match_histogram(self, actualResponse, expectedResponse):
        actualResponse = actualResponse["data"]
        expectedResponse = expectedResponse["data"]
        if "_aggregation" not in actualResponse.keys():
            logger.error("_aggregation is missing from response data")
        if "subject" not in actualResponse["_aggregation"].keys():
            logger.error("subject is missing from response data")

        for key in expectedResponse["_aggregation"]["subject"].keys():
            if key not in actualResponse["_aggregation"]["subject"]:
                logger.error("{} is missing from response data".format(key))
            actualResponseHistogramList = actualResponse["_aggregation"]["subject"][
                key
            ]["histogram"]
            expectedResponseHistogramList = expectedResponse["_aggregation"]["subject"][
                key
            ]["histogram"]
            # Check length of actualResponse and expectedResponse histogram lists are equal
            assert len(expectedResponseHistogramList) == len(
                actualResponseHistogramList
            )
            for item in expectedResponseHistogramList:
                # Check each list item in expectedResponse is present in actualResponse
                if item not in actualResponseHistogramList:
                    logger.error("{} is missing from response data".format(item))
        return True

    def match_data_query(self, actualResponse, expectedResponse):
        assert len(actualResponse) == len(expectedResponse)
        for item in expectedResponse:
            if item not in actualResponse:
                logger.error("{} is missing from response data".format(item))
        return True
