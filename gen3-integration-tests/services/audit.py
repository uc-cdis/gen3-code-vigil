import os
import pytest
import requests

from cdislogging import get_logger
import time

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Audit(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}"
        self.API_AUDIT_ENDPOINT = f"{self.BASE_URL}/audit/log"

    def audit_query(
        self, logCategory, userTokenHeader, params, expectedStatus, audit_category
    ):
        url = self.API_AUDIT_ENDPOINT + "/" + logCategory
        url = url + "?" + "&".join(params)
        response = requests.get(url=url, auth=userTokenHeader)
        logger.info(audit_category + " status code : " + str(response.status_code))
        assert expectedStatus == response.status_code
        return True

    def checkQueryResults(
        self, logCategory, userTokenHeader, params, expectedResults, repeat=False
    ):
        url = self.API_AUDIT_ENDPOINT + "/" + logCategory
        url = url + "?" + "&".join(params)
        counter = 0

        while counter < 10:
            time.sleep(30)
            response = requests.get(url=url, auth=userTokenHeader)
            # Get the first record from api json data
            data = response.json()
            # Counter to check response is recieved within 5 mins
            if len(data["data"]) != 0:
                logger.info(data["data"])
                for key, val in expectedResults.items():
                    # Get the first entry of json data
                    assert data["data"][0][key] == expectedResults[key]
                return True
            counter += 1

        logger.error("Waited for 300 seconds but data was not recieved")
        return False
