import json
import os
import pytest
import requests

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class MetadataService(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/mds"
        self.MDS_ENDPOINT = f"{self.BASE_URL}/metadata"
        self.AGG_MDS_ENDPOINT = f"{self.BASE_URL}/aggregate/metadata"

    def get_aggregate_metadata(self, study_id, user="main_account"):
        """Get aggregate mds record for the study id specified"""
        res = requests.get(
            f"{self.AGG_MDS_ENDPOINT}/guid/{study_id}",
            headers=pytest.auth_headers[user],
        )
        assert res.status_code == 200
        return res.json()["gen3_discovery"]

    def create_metadata(self, study_id, study_json, user="main_account"):
        """
        Create study metadata record.
        metadata-aggregate-sync job must be run to update the record in aggregate metadata.
        """
        logger.info(f"Creating study with id {study_id}")
        res = requests.post(
            f"{self.MDS_ENDPOINT}/{study_id}",
            data=json.dumps(study_json),
            headers=pytest.auth_headers[user],
        )
        logger.info(f"Creation request status code - {res.status_code}")
        assert res.status_code == 201

    def update_metadata(self, study_id, study_json, user="main_account"):
        """
        Update study metadata record.
        metadata-aggregate-sync job must be run to update the record in aggregate metadata.
        """
        logger.info(f"Updating study with id {study_id}")
        res = requests.put(
            f"{self.MDS_ENDPOINT}/{study_id}",
            data=json.dumps(study_json),
            headers=pytest.auth_headers[user],
        )
        logger.info(f"Update request status code - {res.status_code}")
        assert res.status_code == 200

    def delete_metadata(self, study_id, user="main_account"):
        """
        Delete study metadata record.
        metadata-aggregate-sync job must be run to update the record in aggregate metadata.
        """
        logger.info(f"Deleting study with id {study_id}")
        res = requests.delete(
            f"{self.MDS_ENDPOINT}/{study_id}",
            headers=pytest.auth_headers[user],
        )
        logger.info(f"Deletion request status code - {res.status_code}")
        assert res.status_code == 200
