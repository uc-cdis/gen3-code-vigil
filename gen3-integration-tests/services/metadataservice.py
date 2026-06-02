import pytest
import requests
from gen3.auth import Gen3Auth
from gen3.metadata import Gen3Metadata
from utils import logger
from utils.misc import retry


class MetadataService(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/mds"
        self.AGG_MDS_ENDPOINT = f"{self.BASE_URL}/aggregate/metadata"

    @retry(times=3, delay=20, exceptions=(AssertionError))
    def get_metadata(self, study_id, user="main_account"):
        """Get mds record for the study id specified"""
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        gen3metadata = Gen3Metadata(auth_provider=auth)
        try:
            response = gen3metadata.get(guid=study_id)
            return response
        except Exception as e:
            raise Exception(f"Unable to get metadata, exception: {e}")

    @retry(times=8, delay=30, exceptions=(AssertionError))
    def get_aggregate_metadata(self, study_id, user="main_account"):
        """Get aggregate mds record for the study id specified"""
        res = requests.get(
            f"{self.AGG_MDS_ENDPOINT}/guid/{study_id}",
            auth=Gen3Auth(refresh_token=pytest.api_keys[user]),
        )
        assert (
            res.status_code == 200
        ), f"Response status code was {res.status_code}: {res.text}"
        return res.json()

    def create_metadata(self, study_id, study_json, user="main_account"):
        """
        Create study metadata record.
        metadata-aggregate-sync job must be run to update the record in aggregate metadata.
        """
        logger.info(f"Creating study with id {study_id}")
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        gen3metadata = Gen3Metadata(auth_provider=auth)
        try:
            response = gen3metadata.create(
                guid=study_id,
                metadata=study_json,
            )
            logger.info(response)
        except Exception as e:
            raise Exception(f"Unable to create metadata, exception: {e}")

    def update_metadata(self, study_id, study_json, user="main_account"):
        """
        Update study metadata record.
        metadata-aggregate-sync job must be run to update the record in aggregate metadata.
        """
        logger.info(f"Updating study with id {study_id}")
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        gen3metadata = Gen3Metadata(auth_provider=auth)
        try:
            response = gen3metadata.update(
                guid=study_id,
                metadata=study_json,
            )
            logger.info(response)
        except Exception as e:
            raise Exception(f"Unable to update metadata, exception: {e}")

    @retry(times=1, delay=30, exceptions=(AssertionError))
    def delete_metadata(self, study_id, user="main_account"):
        """
        Delete study metadata record.
        metadata-aggregate-sync job must be run to update the record in aggregate metadata.
        """
        logger.info(f"Deleting study with id {study_id}")
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        gen3metadata = Gen3Metadata(auth_provider=auth)
        try:
            response = gen3metadata.delete(
                guid=study_id,
            )
            logger.info(response)
        except Exception as e:
            raise Exception(f"Unable to delete metadata, exception: {e}")
