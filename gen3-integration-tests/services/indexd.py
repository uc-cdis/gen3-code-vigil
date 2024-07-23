import pytest
import requests

from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from uuid import uuid4
from utils import logger


class Indexd(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/index/index"

    def create_records(self, records: dict, user="indexing_account", access_token=None):
        """Create new indexd record"""
        if access_token:
            auth = Gen3Auth(access_token=access_token)
        else:
            auth = Gen3Auth(refresh_token=pytest.api_keys[user])
        index = Gen3Index(auth_provider=auth)
        indexed_files = []
        # Create record for each file
        for record_data in records.values():
            record_data.setdefault("did", str(uuid4()))
            try:
                record = index.create_record(**record_data)
                indexed_files.append(record)
            except Exception as e:
                logger.exception(msg=f"Failed indexd submission got exception {e}")
        return indexed_files

    def get_record(self, indexd_guid: str, user="indexing_account", access_token=None):
        """Get record from indexd"""
        if access_token:
            auth = Gen3Auth(access_token=access_token)
        else:
            auth = Gen3Auth(refresh_token=pytest.api_keys[user])
        indexd = Gen3Index(auth_provider=auth)
        try:
            record = indexd.get_record(guid=indexd_guid)
            logger.info(f"Indexd Record found {record}")
            return record
        except Exception:
            logger.exception(msg=f"Cannot find indexd record with did {indexd_guid}")
            raise

    def update_record_via_api(
        self,
        guid: str,
        rev: str,
        data: dict,
        user="indexing_account",
        access_token=None,
    ):
        """Update indexd record"""
        if access_token:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"bearer {access_token}",
            }
        else:
            headers = pytest.auth_headers[user]
        update_res = requests.put(
            f"{self.BASE_URL}/{guid}?rev={rev}",
            json=data,
            headers=headers,
        )
        return update_res.status_code

    # Use this if the indexd record is created/uploaded through gen3-client upload
    def delete_record_via_api(
        self, guid: str, rev: str, user="indexing_account", access_token=None
    ):
        """Delete indexd record if upload is not happening through gen3-sdk"""
        if access_token:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"bearer {access_token}",
            }
        else:
            headers = pytest.auth_headers[user]
        delete_resp = requests.delete(
            f"{self.BASE_URL}/{guid}?rev={rev}", headers=headers
        )
        return delete_resp.status_code

    # Use this if indexd record is created with the sdk client
    def delete_records(self, guids: list, user="indexing_account"):
        """Delete indexd records list via gen3-sdk"""
        for guid in guids:
            user = "indexing_account"
            auth = Gen3Auth(refresh_token=pytest.api_keys[user])
            index = Gen3Index(auth_provider=auth)
            try:
                index.delete_record(guid=guid)
            except Exception as e:
                logger.exception(msg=f"Failed to delete record with guid {guid} : {e}")

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

    def clear_previous_upload_files(self, user="main_account"):
        """Delete indexd record if upload is not happening through gen3-sdk"""
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        url = f"/index/index/?acl=null&authz=null&uploader={pytest.users[user]}"
        response = auth.curl(path=url)
        logger.info(response.json())
        self.delete_records(guids=response.json())
