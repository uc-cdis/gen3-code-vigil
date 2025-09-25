import datetime
import math
import time
from json import JSONDecodeError

import pytest
from gen3.auth import Gen3Auth
from utils import logger
from utils.misc import retry


class Audit(object):
    # Test comment
    def __init__(self):
        self.BASE_ENDPOINT = "/audit"
        self.AUDIT_LOG_ENDPOINT = f"{self.BASE_ENDPOINT}/log"

    @retry(times=3, delay=10, exceptions=(AssertionError))
    def audit_query(self, log_category, user, expected_status, audit_category):
        timestamp = math.floor(time.mktime(datetime.datetime.now().timetuple()))
        params = [
            "start={}".format(timestamp),
            "username={}".format(pytest.users[user]),
        ]
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        url = self.AUDIT_LOG_ENDPOINT + "/" + log_category
        url = url + "?" + "&".join(params)
        response = auth.curl(path=url)
        logger.info(audit_category + " status code : " + str(response.status_code))
        assert (
            expected_status == response.status_code
        ), f"Expected {expected_status} but got {response.status_code}"
        return True

    def check_query_results(self, log_category, user, params, expected_results):
        url = self.AUDIT_LOG_ENDPOINT + "/" + log_category
        url = url + "?" + "&".join(params)
        counter = 0
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)

        while counter < 40:
            time.sleep(30)
            try:
                response = auth.curl(path=url)
                # Get the first record from api json data
                data = response.json()
                logger.info(data)
                # Counter to check response is recieved within 10 mins
                if len(data["data"]) != 0:
                    logger.info(data["data"])
                    for key, val in expected_results.items():
                        # Get the first entry of json data
                        data_returned = data["data"][0][key]
                        expected_data = expected_results[key]
                        if isinstance(expected_data, str):
                            assert (
                                data_returned.lower() == expected_data.lower()
                            ), f"Expected {expected_data.lower()} but got {data_returned.lower()}"
                        else:
                            assert (
                                data_returned == expected_data
                            ), f"Expected {expected_data} but got {data_returned}"
                    return True
            except JSONDecodeError:
                pass
            counter += 1
        logger.error("Waited for 20 minutes but data was not recieved")
        return False
