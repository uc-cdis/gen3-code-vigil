import os
import pytest
import requests

from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from uuid import uuid4
from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Indexd(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/index/index"

    def create_files(self, files: dict, user="indexing_account"):
        """Create new indexd record"""
        auth = Gen3Auth(refresh_token=pytest.api_keys[user])
        index = Gen3Index(auth_provider=auth)
        indexed_files = []
        # Create record for each file
        for file in files:
            logger.info(files[file])
            logger.info(file)
            if "did" not in files[file]:
                files[file]["did"] = str(uuid4())
            # Create data dictionary to provide as argument for Indexd create record function
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
            except Exception:
                logger.exception(msg="Failed indexd submission got exception")
        return indexed_files

    def get_record(self, indexd_guid: str, user="indexing_account"):
        """Get record from indexd"""
        auth = Gen3Auth(refresh_token=pytest.api_keys[user])
        indexd = Gen3Index(auth_provider=auth)
        try:
            logger.debug(indexd_guid)
            record = indexd.get_record(guid=indexd_guid)
            logger.info(f"Indexd Record found {record}")
            return record
        except Exception as e:
            logger.exception(msg=f"Cannot find indexd record {e}")
            raise

    def get_rev(self, json_data: dict):
        """Get revision from indexd record"""
        if json_data is not None:
            return json_data["rev"]
        else:
            # Handle case where json_data is None (optional)
            logger.info("No rev found in the provided data")
            return None  # Or a suitable default value

    def update_record(self, guid: str, rev: str, data: dict, user="indexing_account"):
        """Update indexd record"""
        update_res = requests.put(
            f"{self.BASE_URL}/{guid}?rev={rev}",
            json=data,
            headers=pytest.auth_headers[user],
        )
        return update_res.status_code

    # Use this if the indexd record is created/uploaded through gen3-client upload
    def delete_record(self, guid: str, rev: str, user="indexing_account"):
        """Delete indexd record if upload is not happening through gen3-sdk"""
        delete_resp = requests.delete(
            f"{self.BASE_URL}/{guid}?rev={rev}", headers=pytest.auth_headers[user]
        )
        return delete_resp.status_code

    # Use this if indexd record is created with the sdk client
    def delete_files(self, guids: list, user="indexing_account"):
        """Delete indexd records list via gen3-sdk"""
        for guid in guids:
            user = "indexing_account"
            auth = Gen3Auth(refresh_token=pytest.api_keys[user])
            index = Gen3Index(auth_provider=auth)
            try:
                index.delete_record(guid=guid)
            except Exception as e:
                logger.exception(msg=f"Failed to delete record with guid {guid} : {e}")

    def file_equals(self, res: dict, file_node: dict) -> None:
        logger.info(f"Response data : {res}")
        logger.info(f"File Node with CCs : {file_node.props}")
        errors = []
        if res["hashes"]["md5"] != file_node.props["md5sum"]:
            errors.append(
                f"md5 value mismatch: '{res['hashes']['md5']}' != '{file_node.props['md5sum']}'"
            )
        if res["size"] != file_node.props["file_size"]:
            errors.append(
                f"file_size value mismatch: '{res['size']}' != '{file_node.props['file_size']}'"
            )
        if "urls" not in res.keys():
            errors.append(f"urls keyword missing in {res.keys()}")
        if "urls" in file_node.props.keys():
            if file_node.props["urls"] not in res["urls"]:
                errors.append(
                    f"urls value mismatch: {file_node.props['urls']} not in {res['urls']}"
                )
        if "authz" in file_node.props.keys():
            for authz_val in file_node.props["authz"]:
                if authz_val not in res["authz"]:
                    errors.append(
                        f"{authz_val} not found in authz list: {res['authz']}"
                    )
        if errors:
            logger.error(f"indexd.file_equals(): files do not match: {errors}")
        return len(errors) == 0, errors
