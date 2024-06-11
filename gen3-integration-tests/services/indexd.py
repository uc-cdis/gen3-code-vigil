import json
import pytest
import requests

from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from uuid import uuid4
from utils import logger


class Indexd(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/index/index"

    def create_data_dictionary(self, record: dict):
        if "did" not in record:
            record["did"] = str(uuid4())
        # Create data dictionary to provide as argument for Indexd create record function
        data = {
            "hashes": {"md5": record["md5"]},
            "size": record["size"],
            "file_name": record["filename"],
            "did": record["did"],
        }

        if "link" in record.keys():
            data["urls"] = [record["link"]]
        if "authz" in record.keys():
            data["authz"] = record["authz"]
        if "acl" in record.keys():
            data["acl"] = record["acl"]
        return data

    def create_files(self, files: dict, user="indexing_account", access_token=None):
        """Create new indexd record"""
        if access_token:
            auth = Gen3Auth(endpoint=self.BASE_URL, access_token=access_token)
        else:
            auth = Gen3Auth(refresh_token=pytest.api_keys[user])
        index = Gen3Index(auth_provider=auth)
        indexed_files = []
        # Create record for each file
        for file in files:
            data = self.create_data_dictionary(record=files[file])
            try:
                record = index.create_record(**data)
                indexed_files.append(record)
            except Exception:
                logger.exception(msg="Failed indexd submission got exception")
        return indexed_files

    # TODO : Switch back to SDK call once issue for access_token is resolved
    def create_files_using_access_token(self, files: dict, access_token):
        indexed_files = []
        # Create record for each file
        for file in files:
            data = self.create_data_dictionary(record=files[file])
            data["form"] = "object"
            try:
                record = requests.post(
                    url=f"{self.BASE_URL}",
                    json=data,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"bearer {access_token}",
                    },
                )
                indexed_files.append(record)
            except Exception as e:
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

    # TODO : Switch back to SDK call once issue for access_token is resolved
    def get_record_using_access_token(self, indexd_guid: str, access_token):
        record = requests.get(
            url=f"{self.BASE_URL}/{indexd_guid}",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"bearer {access_token}",
            },
        ).json()
        return record

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

    # TODO : Switch back to SDK call once issue for access_token is resolved
    def update_record_using_access_token(
        self, guid: str, rev: str, data: dict, access_token
    ):
        update_res = requests.put(
            f"{self.BASE_URL}/{guid}?rev={rev}",
            json=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"bearer {access_token}",
            },
        )
        return update_res.status_code

    # Use this if the indexd record is created/uploaded through gen3-client upload
    def delete_record(self, guid: str, rev: str, user="indexing_account"):
        """Delete indexd record if upload is not happening through gen3-sdk"""
        delete_resp = requests.delete(
            f"{self.BASE_URL}/{guid}?rev={rev}", headers=pytest.auth_headers[user]
        )
        return delete_resp.status_code

    def delete_record_using_access_token(self, guid: str, rev: str, access_token):
        delete_resp = requests.delete(
            f"{self.BASE_URL}/{guid}?rev={rev}",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"bearer {access_token}",
            },
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

    def delete_file_indices(self, records: dict):
        for key, val in records.items():
            try:
                indexd_record = self.get_record(indexd_guid=val["did"])
                indexd_rev = self.get_rev(json_data=indexd_record)
                if indexd_rev is None:
                    logger.info("Indexd record returned None")
                    continue
                logger.info(f"{val['did']} found, performing delete.")
                self.delete_record(guid=indexd_record["did"], rev=indexd_rev)
            except Exception as e:
                if "404" not in f"{e}" and "did" not in f"{e}":
                    logger.error(f"404 status code not returned. Exception : {e}")
                    raise
                logger.info("Indexd record not found, no need to perform delete.")

    def file_equals(self, res: dict, file_record: dict) -> None:
        logger.info(f"Response data : {res}")
        logger.info(f"File Node: {file_record.props}")
        errors = []
        if res["hashes"]["md5"] != file_record.props["md5sum"]:
            errors.append(
                f"md5 value mismatch: '{res['hashes']['md5']}' != '{file_record.props['md5sum']}'"
            )
        if res["size"] != file_record.props["file_size"]:
            errors.append(
                f"file_size value mismatch: '{res['size']}' != '{file_record.props['file_size']}'"
            )
        if "urls" not in res.keys():
            errors.append(f"urls keyword missing in {res.keys()}")
        if "urls" in file_record.props.keys():
            if file_record.props["urls"] not in res["urls"]:
                errors.append(
                    f"urls value mismatch: {file_record.props['urls']} not in {res['urls']}"
                )
        if "authz" in file_record.props.keys():
            for authz_val in file_record.props["authz"]:
                if authz_val not in res["authz"]:
                    errors.append(
                        f"{authz_val} not found in authz list: {res['authz']}"
                    )
        if errors:
            logger.error(f"indexd.file_equals(): files do not match: {errors}")
        return len(errors) == 0, errors
