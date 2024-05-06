"""
DATA UPLOAD
"""
import hashlib
import os
import pytest
import random
import string

from cdislogging import get_logger

from services.dataclient import DataClient
from services.fence import Fence
from services.indexd import Indexd

from services.graph import GraphDataTools
from utils import data_upload

from gen3.auth import Gen3Auth
from playwright.sync_api import Page

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))

# Global variables used across TestDataUpload class
rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
file_name = f"qa-upload-file_{rand}.txt"
file_path = f"./{file_name}"
file_content = (
    "this fake data file was generated and uploaded by the integration test suite\n"
)
big_file_name = f"qa-upload-7mb-file_{rand}.txt"
big_file_path = f"./{big_file_name}"


class FileNode:
    def __init__(self, did: str, props: dict) -> None:
        self.did = did
        self.props = props


@pytest.mark.fence
@pytest.mark.indexd
@pytest.mark.sheepdog
class TestDataUpload:
    def setup_method(self, method):
        # Delete local small file created in setup_method
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        sd_tools.delete_nodes()
        # Create a local small file to upload. Store its size and hash
        with open(file_path, "w") as file:
            file.write(file_content)
        # Create a local large file (size 7MB)
        with open(big_file_path, "w") as file:
            file.write(file_content)

    def teardown_method(self, method):
        os.remove(file_path)
        os.remove(big_file_path)

    def test_file_upload_and_download_via_api(self):
        """
        Scenario: Test Upload and Download via api
        Steps:
            1. Get an upload url from fence
            2. Verify metadata can't be linked to a file without hash and size
            3. Upload a file to S3 using url
            4. Verify indexd listener updates the record with correct hash and size
            5. Link metadata to the file via sheepdog
            6. Download the file via fence and check who can download
        """
        fence = Fence()
        indexd = Indexd()
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        created_guids = []
        try:
            file_size = os.path.getsize(file_path)
            file_md5 = hashlib.md5(open(file_path, "rb").read()).hexdigest()

            fence_upload_res = fence.get_upload_url_from_fence(
                file_name, "main_account"
            )
            file_guid = fence_upload_res["guid"]
            created_guids.append(file_guid)
            presigned_url = fence_upload_res["url"]

            # Check blank record was created in indexd
            file_node = FileNode(
                did=file_guid, props={"md5sum": file_md5, "file_size": file_size}
            )

            indexd.get_record(indexd_guid=file_node.did)

            # fail to submit metadata for this file without hash and size
            try:
                metadata_response = sd_tools.submit_graph_and_file_metadata(
                    file_guid, file_size, file_md5
                )
            except Exception as e:
                assert (
                    "400" in f"{e}"
                ), f"Linking metadata to file without hash and size should not be possible.\n{metadata_response}"

            # check that we CANNOT download the file (there is no URL in indexd yet)
            signed_url_res = fence.createSignedUrl(
                id=file_guid, user="main_account", expectedStatus=404
            )
            fence.has_no_url(signed_url_res)

            # Upload the file to the S3 bucket using the presigned URL
            data_upload.upload_file_to_s3(presigned_url, file_path, file_size)

            # wait for the indexd listener to add size, hashes and URL to the record
            data_upload.wait_upload_file_updated_from_indexd_listener(indexd, file_node)

            # Try downloading before linking metadata to the file. It should succeed for the uploader but fail for other users
            # the uploader can now download the file
            signed_url_res = fence.createSignedUrl(
                id=file_guid, user="main_account", expectedStatus=200
            )
            fence.check_file_equals(signed_url_res, file_content)

            # a user who is not the uploader CANNOT download the file
            signed_url_res = fence.createSignedUrl(
                id=file_guid, user="auxAcct1_account", expectedStatus=401
            )

            # submit metadata for this file
            metadata_response = sd_tools.submit_graph_and_file_metadata(
                file_guid, file_size, file_md5
            )

            # a user who is not the uploader can now download the file
            signed_url_res = fence.createSignedUrl(
                id=file_guid, user="auxAcct1_account", expectedStatus=200
            )
            fence.check_file_equals(signed_url_res, file_content)
        finally:
            indexd.delete_files(created_guids)

    def test_user_without_role_cannot_upload(self):
        """
        Scenario: User without role can't upload
        Steps:
            1. Get an upload url from fence for a user that has no role.
            2. No url should be returned from fence.
        """
        fence = Fence()
        fence_upload_res = fence.get_url_for_data_upload(file_name, "auxAcct1_account")
        fence.has_no_url(fence_upload_res)
        assert (
            fence_upload_res.status_code == 403
        ), f"This user should not be able to download.\n{fence_upload_res.content}"

    @pytest.mark.wip("Test case in development")
    def test_file_upload_download_via_client(self):
        fence = Fence()
        dataclient = DataClient()
        dataclient.configure_client(fence=fence, user="main_account", files=None)

    def test_data_file_deletion(self):
        """
        Scenario: Test Upload and Download via api
        Steps:
            1. Get an upload url from fence
            2. Upload a file to S3 using url
            3. Verify indexd listener updates the record with correct hash and size
            4. Check that a user who is not the uploader cannot delete the file
            5. Delete the file
            6. Verify metadata can't be linked to file after delete
            7. Verify signed url can't be created now
        """
        fence = Fence()
        indexd = Indexd()
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        created_guids = []
        try:
            file_size = os.path.getsize(file_path)
            file_md5 = hashlib.md5(open(file_path, "rb").read()).hexdigest()

            fence_upload_res = fence.get_upload_url_from_fence(
                file_name, "main_account"
            )
            file_guid = fence_upload_res["guid"]
            created_guids.append(file_guid)
            presigned_url = fence_upload_res["url"]

            # Upload the file to the S3 bucket using the presigned URL
            data_upload.upload_file_to_s3(presigned_url, file_path, file_size)

            file_node = FileNode(
                did=file_guid, props={"md5sum": file_md5, "file_size": file_size}
            )

            # wait for the indexd listener to add size, hashes and URL to the record
            data_upload.wait_upload_file_updated_from_indexd_listener(indexd, file_node)

            # check that a user who is not the uploader cannot delete the file
            record = indexd.get_record(created_guids[0])
            rev = indexd.get_rev(json_data=record)
            response = indexd.delete_record(
                guid=created_guids[0], rev=rev, user="auxAcct1_account"
            )
            assert (
                response == 401
            ), "File deletion from user who is not file uploader should not be possible"

            # delete the file
            response = fence.delete_file(guid=created_guids[0], user="main_account")
            assert response == 204, f"File not deleted. Response : {response}"

            # no metadata linking after delete
            try:
                metadata_response = sd_tools.submit_graph_and_file_metadata(
                    file_guid, file_size, file_md5
                )
            except Exception as e:
                assert (
                    "400" in f"{e}"
                ), f"Linking metadata to file without hash and size should not be possible.\n{metadata_response}"

            # no download after delete
            fence.createSignedUrl(id=file_guid, user="main_account", expectedStatus=404)
        finally:
            indexd.delete_files(created_guids)

    def test_upload_the_same_file_twice(self):
        """
        Scenario: Upload the same file twice
        Steps:
            1. Get an upload url from fence
            2. Upload a file to S3 using url
            3. Verify indexd listener updates the record with correct hash and size
            4. Submit metadata for the file
            5. Check the file can be downloaded
            6. Repeat step 1-3 again for same file.
            7. Submit metadata with Create New Parents options
            8. Verify the file can be downloaded
        """
        fence = Fence()
        indexd = Indexd()
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(
            auth=auth, program_name="jnkns", project_code="jenkins"
        )
        created_guids = []
        try:
            file_size = os.path.getsize(file_path)
            file_md5 = hashlib.md5(open(file_path, "rb").read()).hexdigest()

            # First Attempt to Upload file
            fence_upload_res = fence.get_upload_url_from_fence(
                file_name, "main_account"
            )
            file_guid = fence_upload_res["guid"]
            created_guids.append(file_guid)
            presigned_url = fence_upload_res["url"]

            # Upload the file to the S3 bucket using the presigned URL
            data_upload.upload_file_to_s3(presigned_url, file_path, file_size)

            file_node = FileNode(
                did=file_guid, props={"md5sum": file_md5, "file_size": file_size}
            )

            # wait for the indexd listener to add size, hashes and URL to the record
            data_upload.wait_upload_file_updated_from_indexd_listener(indexd, file_node)

            # submit metadata for this file
            metadata_response = sd_tools.submit_graph_and_file_metadata(
                file_guid, file_size, file_md5
            )

            # check that the file can be downloaded
            signed_url_res = fence.createSignedUrl(
                id=file_guid, user="auxAcct1_account", expectedStatus=200
            )
            fence.check_file_equals(signed_url_res, file_content)

            # Second Attempt to Upload file
            fence_upload_res = fence.get_upload_url_from_fence(
                file_name, "main_account"
            )
            file_guid = fence_upload_res["guid"]
            created_guids.append(file_guid)
            presigned_url = fence_upload_res["url"]

            # Upload the file to the S3 bucket using the presigned URL
            data_upload.upload_file_to_s3(presigned_url, file_path, file_size)

            # wait for the indexd listener to add size, hashes and URL to the record
            data_upload.wait_upload_file_updated_from_indexd_listener(indexd, file_node)

            # submit metadata for this file
            # `createNewParents=True` creates new nodes to avoid conflicts with the nodes already submitted by the
            sd_tools.submit_graph_and_file_metadata(
                file_guid,
                file_size,
                file_md5,
                "submitter_id_new_value",
                None,
                True,
            )

            # check that the file can be downloaded
            signed_url_res = fence.createSignedUrl(
                id=file_guid, user="auxAcct1_account", expectedStatus=200
            )
            fence.check_file_equals(signed_url_res, file_content)
        finally:
            indexd.delete_files(created_guids)
