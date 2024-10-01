import os
import pytest
import requests

from utils import logger
from gen3.auth import Gen3Auth
from utils import TEST_DATA_PATH_OBJECT
import requests


class Guppy(object):
    def __init__(self):
        self.BASE_ENDPOINT = "/guppy"

    def validate_guppy_status(self, user, expected_status):
        """
        Validate the status of Guppy
        user - pick one from conftest.py - main_account / indexing_account / auxAcct1_account /
            auxAcct2_account / user0_account
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        url = self.BASE_ENDPOINT + "/_status"
        response = auth.curl(path=url)
        logger.info("Guppy status code : " + str(response.status_code))
        assert expected_status == response.status_code
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
        expected_status,
        endpoint="/graphql",
    ):
        """
        Perform API call using queryFile and validate against responseFile
        queryType - Can be one of the following : mapping / aggregation / historgram / download
        endpoint - Can be one of the following : /graphql or /download
        """
        queryFile = (TEST_DATA_PATH_OBJECT / "guppy" / queryFile).read_text(
            encoding="UTF-8"
        )
        responseFile = (TEST_DATA_PATH_OBJECT / "guppy" / responseFile).read_text(
            encoding="UTF-8"
        )
        queryToSubmit = "".join(queryFile.split("\n"))
        logger.info(queryToSubmit)
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        url = self.BASE_ENDPOINT + endpoint
        headers = {
            "Content-Type": "application/json",
            "Authorization": "bearer {}".format(auth.get_access_token()),
        }
        response = requests.post(
            url=pytest.root_url + url, data=queryToSubmit, headers=headers
        )
        logger.info(f"Status code: {response.status_code}")
        assert expected_status == response.status_code

        # Check queryType and call function accordingly
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
        """ "
        Function to validate API Call output against responseFile
        for Mapping query type
        """
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
        """ "
        Function to validate API Call output against responseFile
        for Aggregation query type
        """
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
        """ "
        Function to validate API Call output against responseFile
        for Histogram query type
        """
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
        """ "
        Function to validate API Call output against responseFile
        for Download/Default query type
        """
        assert len(actualResponse) == len(expectedResponse)
        for item in expectedResponse:
            if item not in actualResponse:
                logger.error("{} is missing from response data".format(item))
        return True
