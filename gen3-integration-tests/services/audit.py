import datetime
import math
import os
import pytest
import time

from utils import logger

from gen3.auth import Gen3Auth

from utils.misc import retry


class Audit(object):
    def __init__(self):
        self.BASE_ENDPOINT = "/audit"
        self.AUDIT_LOG_ENDPOINT = f"{self.BASE_ENDPOINT}/log"

    @retry(times=3, delay=10, exceptions=(AssertionError))
    def audit_query(
        self, log_category, user, user_email, expected_status, audit_category
    ):
        timestamp = math.floor(time.mktime(datetime.datetime.now().timetuple()))
        params = ["start={}".format(timestamp), "username={}".format(user_email)]
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        url = self.AUDIT_LOG_ENDPOINT + "/" + log_category
        url = url + "?" + "&".join(params)
        response = auth.curl(path=url)
        logger.info(audit_category + " status code : " + str(response.status_code))
        assert expected_status == response.status_code
        return True

    def check_query_results(self, log_category, user, params, expected_results):
        url = self.AUDIT_LOG_ENDPOINT + "/" + log_category
        url = url + "?" + "&".join(params)
        counter = 0
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)

        while counter < 20:
            time.sleep(30)
            # response = requests.get(url=url, auth=userTokenHeader)
            response = auth.curl(path=url)
            # Get the first record from api json data
            data = response.json()
            # Counter to check response is recieved within 5 mins
            if len(data["data"]) != 0:
                logger.info(data["data"])
                for key, val in expected_results.items():
                    # Get the first entry of json data
                    assert data["data"][0][key] == expected_results[key]
                return True
            counter += 1

        logger.error("Waited for 10 minutes but data was not recieved")
        return False
