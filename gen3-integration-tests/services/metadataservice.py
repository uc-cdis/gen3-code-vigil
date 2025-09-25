import json
import os

import pytest
import requests
from gen3.auth import Gen3Auth
from utils import logger
from utils.misc import retry


class MetadataService(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/mds"
        self.MDS_ENDPOINT = f"{self.BASE_URL}/metadata"
        self.AGG_MDS_ENDPOINT = f"{self.BASE_URL}/aggregate/metadata"

    @retry(times=3, delay=20, exceptions=(AssertionError))
    def get_metadata(self, study_id, user="main_account"):
        """Get mds record for the study id specified"""
        res = requests.get(
            f"{self.MDS_ENDPOINT}/{study_id}",
            auth=Gen3Auth(refresh_token=pytest.api_keys[user]),
        )
        assert res.status_code == 200, f"Response status code was {res.status_code}"
        return res.json()

    @retry(times=8, delay=30, exceptions=(AssertionError))
    def get_aggregate_metadata(self, study_id, user="main_account"):
        """Get aggregate mds record for the study id specified"""
        res = requests.get(
            f"{self.AGG_MDS_ENDPOINT}/guid/{study_id}",
            auth=Gen3Auth(refresh_token=pytest.api_keys[user]),
        )
        assert res.status_code == 200, f"Response status code was {res.status_code}"
        return res.json()

    def create_metadata(self, study_id, study_json, user="main_account"):
        """
        Create study metadata record.
        metadata-aggregate-sync job must be run to update the record in aggregate metadata.
        """
        logger.info(f"Creating study with id {study_id}")
        res = requests.post(
            f"{self.MDS_ENDPOINT}/{study_id}",
            data=json.dumps(study_json),
            auth=Gen3Auth(refresh_token=pytest.api_keys[user]),
        )
        logger.info(f"Creation request status code - {res.status_code}")
        assert res.status_code == 201, f"Response status code was {res.status_code}"

    def update_metadata(self, study_id, study_json, user="main_account"):
        """
        Update study metadata record.
        metadata-aggregate-sync job must be run to update the record in aggregate metadata.
        """
        logger.info(f"Updating study with id {study_id}")
        res = requests.put(
            f"{self.MDS_ENDPOINT}/{study_id}",
            data=json.dumps(study_json),
            auth=Gen3Auth(refresh_token=pytest.api_keys[user]),
        )
        logger.info(f"Update request status code - {res.status_code}")
        assert res.status_code == 200, f"Response status code was {res.status_code}"

    @retry(times=1, delay=30, exceptions=(AssertionError))
    def delete_metadata(self, study_id, user="main_account"):
        """
        Delete study metadata record.
        metadata-aggregate-sync job must be run to update the record in aggregate metadata.
        """
        logger.info(f"Deleting study with id {study_id}")
        res = requests.delete(
            f"{self.MDS_ENDPOINT}/{study_id}",
            auth=Gen3Auth(refresh_token=pytest.api_keys[user]),
        )
        logger.info(f"Deletion request status code - {res.status_code}")
        assert res.status_code == 200, f"Response status code was {res.status_code}"
