import os
import pytest

from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from uuid import uuid4
from cdislogging import get_logger
from pathlib import Path

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Indexd(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/index"
        self.API_CREDENTIALS_ENDPOINT = f"{self.BASE_URL}/credentials/api"

    def create_files(self, files, user="indexing_account"):
        auth = Gen3Auth(refresh_file=f"{pytest.namespace}_{user}.json")
        index = Gen3Index(auth_provider=auth)
        indexed_files = []
        # Create record for each file
        for file in files:
            logger.info(files[file])
            logger.info(file)
            if "did" not in files[file]:
                files[file]["did"] = str(uuid4())
            # Create data dictionary to provide as arguement for Indexd create record function
            data = {
                "hashes": {"md5": files[file]["md5"]},
                "size": files[file]["size"],
                "file_name": files[file]["filename"],
                "did": files[file]["did"],
                "urls": [files[file]["link"]],
                "authz": files[file]["authz"],
            }

            try:
                logger.info(data)
                record = index.create_record(**data)
                indexed_files.append(record)
            except Exception as e:
                logger.exception(msg="Failed indexd submission got exception")
        return indexed_files

    def delete_files(self, guids):
        # For each guid perform delete operation on indexd
        for guid in guids:
            user = "indexing_account"
            auth = Gen3Auth(refresh_file=f"{pytest.namespace}_{user}.json")
            index = Gen3Index(auth_provider=auth)
            try:
                index.delete_record(guid=guid)
            except Exception as e:
                logger.exception(msg=f"Failed to delete record with guid {guid}")
