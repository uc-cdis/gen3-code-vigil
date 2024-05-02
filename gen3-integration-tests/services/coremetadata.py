import json
import os
import pytest
import requests

from cdislogging import get_logger

from gen3.auth import Gen3Auth

from packaging.version import Version

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class CoreMetaData(object):
    def __init__(self):
        self.BASE_VERSION_ENDPOINT = "/api/search/_version"

    def get_core_metadata(
        self,
        file,
        user,
        format="application/json",
        expected_status=200,
        invalid_authorization=False,
    ):
        min_sem_ver = "3.2.0"
        min_monthly_release = "2023.04.0"
        monthly_release_cutoff = "2020"

        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        response = auth.curl(path=self.BASE_VERSION_ENDPOINT)
        peregrine_version = response.json()["version"]
        url = f"{pytest.root_url}/api/search/coremetadata/"

        if peregrine_version:
            try:
                if Version(peregrine_version) < Version(min_sem_ver) or (
                    Version(peregrine_version) >= Version(monthly_release_cutoff)
                    and Version(peregrine_version) < Version(min_monthly_release)
                ):
                    # Legacy endpoint
                    url = "{pytest.root_url}/coremetadata/"
            except:
                logger.error(
                    "Can't parse or compare the peregrine version: don't user legacy url"
                )

        authorization = f"bearer {auth.get_access_token()}"
        if invalid_authorization:
            authorization = "invalid"
        headers = {
            "Authorization": authorization,
            "Accept": format,
        }
        response = requests.get(url=url + file.indexd_guid, headers=headers)
        assert response.status_code == expected_status, f"{response}"
        return response

    def see_bibtex_core_metadata(self, file, metadata):
        metadata = metadata.content.decode()
        assert (
            file.props["file_name"] in metadata
        ), f"file_name not matched/found.\n{file}\n{metadata}"
        assert (
            file.indexd_guid in metadata
        ), f"object_id not matched/found.\n{file}\n{metadata}"
        assert (
            file.props["type"] in metadata
        ), f"type not matched/found.\n{file}\n{metadata}"
        assert (
            file.props["data_format"] in metadata
        ), f"data_format not matched/found.\n{file}\n{metadata}"

    def see_core_metadata_error(self, metadata, message):
        if "message" not in metadata.json().keys():
            logger.error(f"Message key missing.\n{metadata.json()}")
            raise
        logger.info(metadata.json()["message"])
        if message != metadata.json()["message"]:
            logger.error(f"Expected message not found.\n{metadata.json()}")
            raise
