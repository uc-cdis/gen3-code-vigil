"""
DATA UPLOAD
"""

import hashlib
import math
import os
import random
import string

import pytest
from cdislogging import get_logger
from gen3.auth import Gen3Auth
from pages.login import LoginPage
from pages.submission import SubmissionPage
from playwright.sync_api import Page
from services.fence import Fence
from services.graph import GraphDataTools
from services.indexd import Indexd

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def create_large_file(filePath, megabytes, text):
    with open(filePath, mode="w") as f:
        # 1MB = 1024 times the previous text
        for i in range(megabytes * 1024):
            f.write(text)


# Global variables used across TestDataUpload class
rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
file_name = f"qa-upload-file_{rand}.txt"
file_path = f"./{file_name}"
text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Morbi sit amet iaculis neque, at mattis mi. Donec pharetra lacus sit amet dui tincidunt, a varius risus tempor. Duis dictum sodales dignissim. Ut luctus turpis non nibh pretium consequat. Fusce faucibus vulputate magna vel congue. Proin sit amet libero mauris. Lorem ipsum dolor sit amet, consectetur adipiscing elit. In sed dictum lacus. Vestibulum bibendum ipsum quis lacus dignissim euismod. Mauris et dignissim leo. Phasellus pretium molestie nunc, varius gravida augue congue quis. Maecenas faucibus, velit dignissim feugiat viverra, eros diam tempor tortor, sed maximus mi justo a massa. Mauris at metus tincidunt augue iaculis mollis et id eros. Interdum et malesuada fames ac ante ipsum primis in faucibus. Aliquam sagittis porta vestibulum. Cras molestie nulla metus, a sollicitudin neque suscipit nec. Nunc sem lectus, molestie eu mauris eget, volutpat posuere mauris. Donec gravida venenatis sodales. Pellentesque risus lorem, pulvinar nec molestie eu amet. "
file_content = (
    "this fake data file was generated and uploaded by the integration test suite1\n"
)
big_file_name = f"qa-upload-7mb-file_{rand}.txt"
big_file_path = f"./{big_file_name}"


class FileRecord:
    def __init__(self, did: str, props: dict) -> None:
        self.did = did
        self.props = props


class FileRecordWithCCs:
    def __init__(self, did: str, props: dict, authz: list) -> None:
        self.did = did
        self.props = props
        self.authz = authz


@pytest.mark.skipif(
    "fence" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.skipif(
    "indexd" not in pytest.deployed_services,
    reason="indexd service is not running on this environment",
)
@pytest.mark.skipif(
    "sheepdog" not in pytest.deployed_services,
    reason="sheepdog service is not running on this environment",
)
@pytest.mark.skipif(
    "ssjdispatcher" not in pytest.deployed_services,
    reason="ssjdispatcher service is not running on this environment",
)
@pytest.mark.skipif(
    "metadata" not in pytest.deployed_services,
    reason="Metadata service is not running on this environment",
)
@pytest.mark.fence
@pytest.mark.indexd
@pytest.mark.graph_submission
@pytest.mark.data_upload
class TestDataUpload:
    @classmethod
    def setup_class(cls):
        cls.auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        cls.sd_tools = GraphDataTools(
            auth=cls.auth, program_name="DEV", project_code="test"
        )
        cls.fence = Fence()
        cls.indexd = Indexd()
        cls.login_page = LoginPage()
        cls.submission = SubmissionPage()
        cls.created_guids = []

        # Create the graph record for core_metadata_collection
        cls.sd_tools.delete_all_records()
        node_name = "core_metadata_collection"
        cls.sd_tools.submit_new_record(node_name)

        # Clear previously uploaded files
        cls.indexd.clear_previous_upload_files(user="main_account")
        cls.indexd.clear_previous_upload_files(user="user1_account")
        cls.indexd.clear_previous_upload_files(user="indexing_account")

    @classmethod
    def teardown_class(cls):
        cls.sd_tools.delete_all_records()

    def setup_method(self, method):
        # Create a local small file to upload. Store its size and hash
        with open(file_path, "w") as file:
            file.write(file_content)
        # Create a local large file (size 7MB)
        create_large_file(big_file_path, 7, text)

        node_name = "core_metadata_collection"
        self.sd_tools.submit_new_record(node_name)

    def teardown_method(self, method):
        os.remove(file_path)
        os.remove(big_file_path)
        # Delete all test records at the end of each test
        self.sd_tools.delete_all_records()
        # Delete all guids
        self.indexd.delete_records(self.created_guids)
        self.created_guids = []

    @pytest.mark.skipif(
        not pytest.indexs3client_job_deployed,
        reason="indexs3client job is not deployed as per manifest.json",
    )
    def test_file_upload_with_consent_codes(self):
        """
        Scenario: File upload with consent codes
        Steps:
            1. Get an upload url from fence
            2. Verify metadata can't be linked to a file without hash and size
            3. Upload a file to S3 using url
            4. Verify indexd listener updates the record with correct hash and size
            5. Link metadata to the file via sheepdog
            6. Download the file via fence and check who can download
        """
        metadata = self.sd_tools.get_file_record()
        if "consent_codes" not in metadata.props.keys():
            pytest.skip(
                "Skipping consent code tests since dictionary does not have them"
            )
        file_size = os.path.getsize(file_path)
        file_md5 = hashlib.md5(open(file_path, "rb").read()).hexdigest()
        fence_upload_res = self.fence.get_url_for_data_upload(
            file_name, "main_account"
        ).json()
        file_guid = fence_upload_res["guid"]
        self.created_guids.append(file_guid)
        presigned_url = fence_upload_res["url"]

        # Check blank record was created in indexd
        file_record = FileRecord(
            did=file_guid, props={"md5sum": file_md5, "file_size": file_size}
        )
        self.indexd.get_record(indexd_guid=file_record.did)

        # Upload the file to the S3 bucket using the presigned URL
        self.fence.upload_file_using_presigned_url(presigned_url, file_path, file_size)

        # wait for the indexd listener to add size, hashes and URL to the record
        self.fence.wait_upload_file_updated_from_indexd_listener(
            self.indexd, file_record
        )

        # submit metadata for this file
        file_type_node = self.sd_tools.get_file_record()
        file_type_node.props["object_id"] = file_guid
        file_type_node.props["file_size"] = file_size
        file_type_node.props["md5sum"] = file_md5
        file_type_node.props["consent_codes"] = ["cc1", "cc_2"]
        self.sd_tools.submit_links_for_record(file_type_node)
        self.sd_tools.submit_record(record=file_type_node)
        file_record_with_ccs = FileRecordWithCCs(
            did=file_guid,
            props={"md5sum": file_md5, "file_size": file_size},
            authz=["/consents/cc1", "/consents/cc_2"],
        )
        self.fence.wait_upload_file_updated_from_indexd_listener(
            self.indexd, file_record_with_ccs
        )

    @pytest.mark.skipif(
        not pytest.indexs3client_job_deployed,
        reason="indexs3client job is not deployed as per manifest.json",
    )
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
        file_size = os.path.getsize(file_path)
        file_md5 = hashlib.md5(open(file_path, "rb").read()).hexdigest()
        fence_upload_res = self.fence.get_url_for_data_upload(
            file_name, "main_account"
        ).json()
        file_guid = fence_upload_res["guid"]
        self.created_guids.append(file_guid)
        presigned_url = fence_upload_res["url"]

        # Check blank record was created in indexd
        file_record = FileRecord(
            did=file_guid, props={"md5sum": file_md5, "file_size": file_size}
        )
        self.indexd.get_record(indexd_guid=file_record.did)

        # fail to submit metadata for this file without hash and size
        try:
            file_type_node = self.sd_tools.get_file_record()
            file_type_node.props["object_id"] = file_guid
            file_type_node.props["file_size"] = file_size
            file_type_node.props["md5sum"] = file_md5
            self.sd_tools.submit_links_for_record(file_type_node)
            self.sd_tools.submit_record(record=file_type_node)
        except Exception as e:
            assert (
                "400" in f"{e}"
            ), f"Linking metadata to file without hash and size should not be possible."

        # check that we CANNOT download the file (there is no URL in indexd yet)
        signed_url_res = self.fence.create_signed_url(
            id=file_guid, user="main_account", expected_status=404
        )
        assert (
            "url" not in signed_url_res.content.decode()
        ), f"URL key is missing.\n{signed_url_res}"

        # Upload the file to the S3 bucket using the presigned URL
        self.fence.upload_file_using_presigned_url(presigned_url, file_path, file_size)

        # wait for the indexd listener to add size, hashes and URL to the record
        self.fence.wait_upload_file_updated_from_indexd_listener(
            self.indexd, file_record
        )

        # Try downloading before linking metadata to the file. It should succeed for the uploader but fail for other users
        # the uploader can now download the file
        signed_url_res = self.fence.create_signed_url(
            id=file_guid, user="main_account", expected_status=200
        )
        self.fence.check_file_equals(signed_url_res, file_content)

        # a user who is not the uploader CANNOT download the file
        signed_url_res = self.fence.create_signed_url(
            id=file_guid, user="smarty_two", expected_status=401
        )

        # submit metadata for this file
        file_type_node = self.sd_tools.get_file_record()
        file_type_node.props["object_id"] = file_guid
        file_type_node.props["file_size"] = file_size
        file_type_node.props["md5sum"] = file_md5
        self.sd_tools.submit_links_for_record(file_type_node)
        self.sd_tools.submit_record(record=file_type_node)

        # a user who is not the uploader can now download the file
        signed_url_res = self.fence.create_signed_url(
            id=file_guid, user="smarty_two", expected_status=200
        )
        self.fence.check_file_equals(signed_url_res, file_content)

    def test_user_without_role_cannot_upload(self):
        """
        Scenario: User without role can't upload
        Steps:
            1. Get an upload url from fence for a user that has no role.
            2. No url should be returned from fence.
        """
        fence_upload_res = self.fence.get_url_for_data_upload(file_name, "dummy_one")
        assert (
            "url" not in fence_upload_res.content.decode()
        ), f"URL key is missing.\n{fence_upload_res}"
        assert (
            fence_upload_res.status_code == 403
        ), f"This user should not be able to download.\n{fence_upload_res.content}"

    @pytest.mark.skipif(
        not pytest.indexs3client_job_deployed,
        reason="indexs3client job is not deployed as per manifest.json",
    )
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
        file_size = os.path.getsize(file_path)
        file_md5 = hashlib.md5(open(file_path, "rb").read()).hexdigest()
        fence_upload_res = self.fence.get_url_for_data_upload(
            file_name, "main_account"
        ).json()
        file_guid = fence_upload_res["guid"]
        self.created_guids.append(file_guid)
        presigned_url = fence_upload_res["url"]

        # Upload the file to the S3 bucket using the presigned URL
        self.fence.upload_file_using_presigned_url(presigned_url, file_path, file_size)
        file_record = FileRecord(
            did=file_guid, props={"md5sum": file_md5, "file_size": file_size}
        )

        # wait for the indexd listener to add size, hashes and URL to the record
        self.fence.wait_upload_file_updated_from_indexd_listener(
            self.indexd, file_record
        )

        # check that a user who is not the uploader cannot delete the file
        record = self.indexd.get_record(self.created_guids[-1])
        rev = record.get("rev", None)
        response = self.indexd.delete_record_via_api(
            guid=self.created_guids[-1], rev=rev, user="smarty_two"
        )
        assert (
            response == 401
        ), "File deletion from user who is not file uploader should not be possible"

        # delete the file
        response = self.fence.delete_file(
            guid=self.created_guids[-1], user="main_account"
        )
        assert response == 204, f"File not deleted. Response : {response}"

        # no metadata linking after delete
        try:
            file_record = self.sd_tools.get_file_record()
            file_record.props["object_id"] = file_guid
            file_record.props["file_size"] = file_size
            file_record.props["md5sum"] = file_md5
            self.sd_tools.submit_links_for_record(file_record)
            self.sd_tools.submit_record(record=file_record)
        except Exception as e:
            assert (
                "400" in f"{e}"
            ), f"Linking metadata to file without hash and size should not be possible.\n{metadata_response}"

        # no download after delete
        self.fence.create_signed_url(
            id=file_guid, user="main_account", expected_status=404
        )

    @pytest.mark.skipif(
        not pytest.indexs3client_job_deployed,
        reason="indexs3client job is not deployed as per manifest.json",
    )
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
        file_size = os.path.getsize(file_path)
        file_md5 = hashlib.md5(open(file_path, "rb").read()).hexdigest()

        # First Attempt to Upload file
        fence_upload_res = self.fence.get_url_for_data_upload(
            file_name, "main_account"
        ).json()
        file_guid = fence_upload_res["guid"]
        self.created_guids.append(file_guid)
        presigned_url = fence_upload_res["url"]

        # Upload the file to the S3 bucket using the presigned URL
        self.fence.upload_file_using_presigned_url(presigned_url, file_path, file_size)
        file_record = FileRecord(
            did=file_guid, props={"md5sum": file_md5, "file_size": file_size}
        )

        # wait for the indexd listener to add size, hashes and URL to the record
        self.fence.wait_upload_file_updated_from_indexd_listener(
            self.indexd, file_record
        )

        # submit metadata for this file
        file_type_node = self.sd_tools.get_file_record()
        file_type_node.props["object_id"] = file_guid
        file_type_node.props["file_size"] = file_size
        file_type_node.props["md5sum"] = file_md5
        self.sd_tools.submit_links_for_record(file_type_node)
        self.sd_tools.submit_record(record=file_type_node)

        # check that the file can be downloaded
        signed_url_res = self.fence.create_signed_url(
            id=file_guid, user="smarty_two", expected_status=200
        )
        self.fence.check_file_equals(signed_url_res, file_content)

        # Second Attempt to Upload file
        fence_upload_res = self.fence.get_url_for_data_upload(
            file_name, "main_account"
        ).json()
        file_guid = fence_upload_res["guid"]
        self.created_guids.append(file_guid)
        presigned_url = fence_upload_res["url"]

        # Upload the file to the S3 bucket using the presigned URL
        self.fence.upload_file_using_presigned_url(presigned_url, file_path, file_size)

        # wait for the indexd listener to add size, hashes and URL to the record
        self.fence.wait_upload_file_updated_from_indexd_listener(
            self.indexd, file_record
        )

        # submit metadata for this file
        # generate new graph data and use that to submit the same file again
        self.sd_tools.regenerate_graph_data()
        file_type_node = self.sd_tools.get_file_record()
        file_type_node.props["object_id"] = file_guid
        file_type_node.props["file_size"] = file_size
        file_type_node.props["md5sum"] = file_md5
        file_type_node.props["submitter_id"] = "submitter_id_new_value"
        self.sd_tools.submit_links_for_record(file_type_node)

        self.sd_tools.submit_record(record=file_type_node)
        # check that the file can be downloaded
        signed_url_res = self.fence.create_signed_url(
            id=file_guid, user="smarty_two", expected_status=200
        )
        self.fence.check_file_equals(signed_url_res, file_content)

    @pytest.mark.skipif(
        not pytest.indexs3client_job_deployed,
        reason="indexs3client job is not deployed as per manifest.json",
    )
    def test_successful_multipart_upload(self):
        """
        Scenario: Successful multipart upload
        Steps:
            1. Generate a 7MB file.
            2. Perform an initialize multipart upload for the file.
            3. Split the file data into 2 parts.
            4. Generate url for multipart upload.
            5. Upload the data using the fence presigned url.
            6. Complete the multipart upload.
            7. Create a signed url using the same guid id as in previous steps.
            8. Verify the contents of the file are correct.
        """
        # Generate a 7MB file.
        file_size = os.path.getsize(big_file_path)
        file_md5 = hashlib.md5(open(big_file_path, "rb").read()).hexdigest()
        with open(big_file_path, "r") as file:
            file_contents = file.read()
        # Split the file data into 2 parts.
        five_mb_length = math.floor(len(file_contents * 5) / 7)
        big_file_parts = {
            1: file_contents[0:five_mb_length],
            2: file_contents[five_mb_length:],
        }

        # Perform an initialize multipart upload for the file.
        init_multipart_upload_res = self.fence.initialize_multipart_upload(
            big_file_name, user="main_account"
        )
        assert (
            "guid" in init_multipart_upload_res.keys()
        ), f"Expected guid key not found. {init_multipart_upload_res}"
        assert (
            "uploadId" in init_multipart_upload_res.keys()
        ), f"Expected uploadId key not found. {init_multipart_upload_res}"

        file_guid = init_multipart_upload_res["guid"]
        self.created_guids.append(file_guid)
        key = f"{file_guid}/{big_file_name}"
        parts_summary = []

        for part_number, val in big_file_parts.items():
            # Generate url for multipart upload.
            multipart_upload_res = self.fence.get_url_for_multipart_upload(
                key=key,
                upload_id=init_multipart_upload_res["uploadId"],
                part_number=part_number,
                user="main_account",
            )
            # Upload the data using the fence presigned url.
            etag = self.fence.upload_data_using_presigned_url(
                presigned_url=multipart_upload_res["presigned_url"], file_data=val
            )
            parts_summary.append({"PartNumber": part_number, "ETag": etag})

        # Complete the multipart upload.
        status_code = self.fence.complete_multipart_upload(
            key=key,
            upload_id=init_multipart_upload_res["uploadId"],
            parts=parts_summary,
            user="main_account",
        )
        assert status_code == 200, f"Expected status 200 but got {status_code}"

        file_record = FileRecord(
            did=file_guid, props={"md5sum": file_md5, "file_size": file_size}
        )

        self.fence.wait_upload_file_updated_from_indexd_listener(
            self.indexd, file_record
        )

        # Create a signed url using the same guid id as in previous steps.
        signed_url_res = self.fence.create_signed_url(
            id=file_guid, user="main_account", expected_status=200
        )

        # Verify the contents of the file are correct.
        self.fence.check_file_equals(signed_url_res, file_contents)

    def test_failed_multipart_upload(self):
        """
        Scenario: Failed multipart upload
        Steps:
            1. Generate a 7MB file.
            2. Perform an initialize multipart upload for the file.
            3. Split the file data into 2 parts.
            4. Generate url for multipart upload.
            5. Upload the data using the fence presigned url.
            6. Complete the multipart upload using a fake ETag, which should fail.
            7. Create a signed url using the same guid id as in previous steps, which shouldn't get created.
        """
        # Generate a 7MB file.
        with open(big_file_path, "r") as file:
            file_contents = file.read()
        # Split the file data into 2 parts.
        five_mb_length = math.floor(len(file_contents * 5) / 7)
        big_file_parts = {
            1: file_contents[0:five_mb_length],
            2: file_contents[five_mb_length:],
        }

        # Perform an initialize multipart upload for the file.
        init_multipart_upload_res = self.fence.initialize_multipart_upload(
            big_file_name, user="main_account"
        )
        assert (
            "guid" in init_multipart_upload_res.keys()
        ), f"Expected guid key not found. {init_multipart_upload_res}"
        assert (
            "uploadId" in init_multipart_upload_res.keys()
        ), f"Expected uploadId key not found. {init_multipart_upload_res}"

        file_guid = init_multipart_upload_res["guid"]
        self.created_guids.append(file_guid)
        key = f"{file_guid}/{big_file_name}"
        parts_summary = []

        for part_number, val in big_file_parts.items():
            # Generate url for multipart upload.
            multipart_upload_res = self.fence.get_url_for_multipart_upload(
                key=key,
                upload_id=init_multipart_upload_res["uploadId"],
                part_number=part_number,
                user="main_account",
            )
            # Upload the data using the fence presigned url.
            etag = self.fence.upload_data_using_presigned_url(
                presigned_url=multipart_upload_res["presigned_url"], file_data=val
            )
            parts_summary.append({"PartNumber": part_number, "ETag": f"{etag}fake"})

        # Complete the multipart upload using a fake ETag, which should fail.
        status_code = self.fence.complete_multipart_upload(
            key=key,
            upload_id=init_multipart_upload_res["uploadId"],
            parts=parts_summary,
            user="main_account",
        )

        assert (
            status_code != 200
        ), f"Expected status to not be 200, but got {status_code}"

        # Create a signed url using the same guid id as in previous steps, which shouldn't get created.
        self.fence.create_signed_url(
            id=file_guid, user="main_account", expected_status=404
        )

    @pytest.mark.portal
    @pytest.mark.skipif(
        "midrc" in os.getenv("UPDATED_FOLDERS", "") or "midrc" in pytest.hostname,
        reason="data upload UI test cases don't work in midrc environment",
    )
    @pytest.mark.skipif(
        not pytest.indexs3client_job_deployed,
        reason="indexs3client job is not deployed as per manifest.json",
    )
    def test_map_uploaded_files_in_submission_page(self, page: Page):
        """
        Scenario: Map uploaded files in windmill submission page
        Steps:
            1. Create a presigned url for uploading the file with main_account
            2. Goto submission page and verify "1 files | 0 B" entry is available under unmapped files section
            3. Upload the file using the presigned url
            4. Goto submission page and verify "1 files | 128 B" entry is available under unmapped files section
            5. Perform mapping by going to submission/files endpoint
            6. Verify no files are present under unmapped files section
        """
        file_object = {
            "file_name": file_name,
            "file_path": file_path,
            "file_size": os.path.getsize(file_path),
            "file_md5": hashlib.md5(file_content.encode()).hexdigest(),
        }

        fence_upload_res = self.fence.get_url_for_data_upload(
            file_name, "main_account"
        ).json()
        assert (
            "url" in fence_upload_res.keys()
        ), f"Expected guid key not found. {fence_upload_res}"
        file_guid = fence_upload_res["guid"]
        self.created_guids.append(file_guid)
        presigned_url = fence_upload_res["url"]
        logger.info(file_guid)
        logger.info(presigned_url)

        self.login_page.go_to(page)
        self.login_page.login(page)
        # user should see 1 file, but not ready yet
        self.submission.check_unmapped_files_submission_page(page, text="1 files | 0 B")

        self.fence.upload_file_using_presigned_url(
            presigned_url, file_object, file_object["file_size"]
        )

        # user should see 1 file ready
        self.login_page.go_to(page)
        self.submission.check_unmapped_files_submission_page(
            page, text="1 files | 128 B"
        )

        # Perform mapping
        self.submission.map_files(page)
        self.submission.select_submission_fields(page)

        # user should see 0 file ready
        self.submission.check_unmapped_files_submission_page(page, text="0 files | 0 B")

        self.login_page.logout(page)

    @pytest.mark.portal
    @pytest.mark.skipif(
        "midrc" in os.getenv("UPDATED_FOLDERS", "") or "midrc" in pytest.hostname,
        reason="data upload UI test cases don't work in midrc environment",
    )
    def test_cannot_see_files_uploaded_by_other_users(self, page: Page):
        """
        Scenario: Cannot see files uploaded by other users
        Steps:
            1. Create a presigned url for uploading the file with user1_account
            2. Upload the file using the presigned url
            3. Goto submission page and verify no files are present under unmapped files.
        """
        file_object = {
            "file_name": file_name,
            "file_path": file_path,
            "file_size": os.path.getsize(file_path),
            "file_md5": hashlib.md5(file_content.encode()).hexdigest(),
        }

        fence_upload_res = self.fence.get_url_for_data_upload(
            file_name, "user1_account"
        ).json()
        assert (
            "url" in fence_upload_res.keys()
        ), f"Expected guid key not found. {fence_upload_res}"
        file_guid = fence_upload_res["guid"]
        self.created_guids.append(file_guid)
        presigned_url = fence_upload_res["url"]

        # Upload the file using user1_accounts presgined url
        self.fence.upload_file_using_presigned_url(
            presigned_url, file_object, file_object["file_size"]
        )

        self.login_page.go_to(page)
        self.login_page.login(page)
        self.submission.check_unmapped_files_submission_page(page, text="0 files | 0 B")
        self.login_page.logout(page)
