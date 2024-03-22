import os

from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from uuid import uuid4
from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Indexd(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/index"
        self.API_CREDENTIALS_ENDPOINT = f"{self.BASE_URL}/credentials/api"

    def index_files(self, api_key, files):
        auth = Gen3Auth(refresh_file=api_key)
        index = Gen3Index(auth_provider=auth)
        indexed_files = []
        for file in files:
            if not file.did:
                file.did = str(uuid4())
            data = {
                "file_name": file.filename,
                "did": file.did,
                "form": "object",
                "size": file.size,
                "urls": [],
                "hashes": {"md5": file.md5},
                "acl": file.acl,
                "metadata": file.metadata,
            }

            if hasattr(file, "urls"):
                data["urls"] = file.urls
            elif hasattr(file, "link"):
                data["urls"] = [file.link]
            else:
                data["urls"] = []

            if hasattr(file, "authz"):
                data["authz"] = file.authz
            try:
                record = index.create_record(**file)
                indexed_files.append(record)
            except Exception as e:
                logger.exception(msg="Failed indexd submission got exception")
        return indexed_files

    def delete_files(self, api_key, guids):
        for guid in guids:
            auth = Gen3Auth(refresh_file=api_key)
            index = Gen3Index(auth_provider=auth)
            try:
                index.delete_record(guid=guid)
            except Exception as e:
                logger.exception(msg=f"Failed to delete record with guid {guid}")
