import os
import pytest

from cdislogging import get_logger
from gen3.auth import Gen3Auth
import time
import pandas as pd

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Audit(object):
    def __init__(self):
        self.BASE_ENDPOINT = "/audit"
        self.AUDIT_LOG_ENDPOINT = f"{self.BASE_ENDPOINT}/log"

    def audit_query(self, logCategory, user, params, expectedStatus, audit_category):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        url = self.AUDIT_LOG_ENDPOINT + "/" + logCategory
        url = url + "?" + "&".join(params)
        response = auth.curl(path=url)
        logger.info(audit_category + " status code : " + str(response.status_code))
        assert expectedStatus == response.status_code
        return True

    def checkQueryResults(self, logCategory, user, params, expectedResults):
        url = self.AUDIT_LOG_ENDPOINT + "/" + logCategory
        url = url + "?" + "&".join(params)
        counter = 0
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)

        while counter < 10:
            time.sleep(30)
            # response = requests.get(url=url, auth=userTokenHeader)
            response = auth.curl(path=url)
            # Get the first record from api json data
            data = response.json()
            # Counter to check response is recieved within 5 mins
            if len(data["data"]) != 0:
                # Convert json to dataframe for easy querying of records using username
                df = pd.json_normalize(data["data"])
                df = df.loc[df["username"] == expectedResults["username"]]
                logger.info(df)
                if df.shape[0] != 0:
                    for key, val in expectedResults.items():
                        # Get the first entry of json data
                        assert df.iloc[0][key] == expectedResults[key]
                    return True
            counter += 1

        logger.error("Waited for 300 seconds but data was not recieved")
        return False
