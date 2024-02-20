import os
import pytest
import requests

from cdislogging import get_logger
from playwright.sync_api import expect

from services.fence import Fence
from services.indexd import Indexd
from gen3.auth import Gen3Auth
from gen3.index import Gen3Index
from gen3.file import Gen3File

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.indexd
@pytest.mark.fence
class TestPresignedUrl:
    def test_get_presigned_url(self, index_files, main_auth):
        file = Gen3File(auth_provider=main_auth)
        presigned_url = file.get_presigned_url(index_files["allowed"]["did"], "s3")
        assert presigned_url.get("url")
        resp = requests.get(presigned_url.get("url"))
        assert resp.text == "Hi Zac!\ncdis-data-client uploaded this!\n"

    def test_get_presigned_url_for_user_without_permission(
        self, index_files, main_auth
    ):
        file = Gen3File(auth_provider=main_auth)
        error = file.get_presigned_url(index_files["not_allowed"]["did"])
        assert error == "You don't have access permission on this file"

    def test_get_presigned_url_with_invalid_protocol(self, index_files, main_auth):
        file = Gen3File(auth_provider=main_auth)
        error = file.get_presigned_url(index_files["not_allowed"]["did"], protocol="s2")
        assert error == "The specified protocol s2 is not supported"

    def test_get_presigned_url_with_unavailable_protocol(self, index_files, main_auth):
        file = Gen3File(auth_provider=main_auth)
        error = file.get_presigned_url(index_files["allowed"]["did"], protocol="s2")
        assert (
            error
            == f"File {index_files['allowed']['did']} does not have a location with specified protocol s3."
        )

    def test_get_presigned_url_no_data(self, index_files, main_auth):
        file = Gen3File(auth_provider=main_auth)
        error = file.get_presigned_url(index_files["no_link"]["did"], protocol="s3")
        assert (
            error
            == f"File {index_files['no_link']['did']} does not have a location with specified protocol s3."
        )

    def test_get_presigned_url_no_requested_protocol_no_data(
        self, index_files, main_auth
    ):
        file = Gen3File(auth_provider=main_auth)
        error = file.get_presigned_url(index_files["no_link"]["did"])
        assert error == "Can't find any file locations."

    @pytest.fixture(scope="class")
    def index_files(self, indexing_auth):
        files = {
            "allowed": {
                "file_name": "test_valid",
                "urls": ["s3://cdis-presigned-url-test/testdata"],
                "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
                "acl": ["jenkins"],
                "size": 9,
            },
            "not_allowed": {
                "file_name": "test_not_allowed",
                "urls": ["s3://cdis-presigned-url-test/testdata"],
                "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
                "acl": ["acct"],
                "size": 9,
            },
            "no_link": {
                "file_name": "test_no_link",
                "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
                "acl": ["jenkins"],
                "size": 9,
            },
            "http_link": {
                "file_name": "test_protocol",
                "urls": ["http://cdis-presigned-url-test/testdata"],
                "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
                "acl": ["jenkins"],
                "size": 9,
            },
            "invalid_protocol": {
                "file_name": "test_invalid_protocol",
                "urls": ["s2://cdis-presigned-url-test/testdata"],
                "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
                "acl": ["jenkins"],
                "size": 9,
            },
        }
        index = Gen3Index(auth_provider=indexing_auth)
        for key, file in files.items():
            record = index.create_record(**file)
            file["did"] = record["did"]

        yield files

        for file in files.values():
            index.delete_record(file["did"])
