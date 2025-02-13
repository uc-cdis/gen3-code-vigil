import json

import pytest
from services.gen3workflows import Gen3Workflow
from utils import TEST_DATA_PATH_OBJECT


def is_service_missing(service_name: str):
    manifest_path = f"{TEST_DATA_PATH_OBJECT}/configuration/manifest.json"
    manifest_data = json.loads(manifest_path)
    return any(service not in manifest_data["versions"] for service in service_name)


@pytest.mark.skipif(
    is_service_missing("funnel"),
    reason="funnel service is not running on this environment",
)
@pytest.mark.skipif(
    is_service_missing("gen3-workflow"),
    reason="gen3-workflow is not running on this environment",
)
@pytest.mark.gen3_workflow
class TestGen3Workflow(object):
    gen3_workflow = Gen3Workflow()
    valid_user = "main_account"
    invalid_user = "dummy_one"
    bucket_name = None
    folder_name = "integration-tests"
    file_name = "test-input.txt"

    ######################## Test /storage/info endpoint ########################
    def test_get_storage_info_with_valid_token(self):
        """Test GET /storage/info with a valid access token."""
        response = self.gen3_workflow.get_storage_info(
            user=self.valid_user, expected_status=200
        )
        assert isinstance(response, dict), "Expected a valid JSON response"
        assert (
            "bucket" in response
        ), "Expected the response to contain the `S3 bucket` details"
        self.bucket_name = response["bucket"]

    def test_get_storage_info_without_token(self):
        """Test GET /storage/info without an access token."""
        self.gen3_workflow.get_storage_info(user=None, expected_status=401)

    ######################## Test /s3/ endpoint ########################

    @pytest.mark.skipif(
        not bucket_name,
        reason="Skipping this test, since a valid s3 bucket name couldn't be found ",
    )
    def test_any_user_cannot_get_s3_file_with_unsigned_request(self):
        """Unsigned requests should receive 401 even if the user is authorized to get data."""
        self.gen3_workflow.get_bucket_object_with_unsigned_request(
            object_path=f"{self.bucket_name}/{self.folder_name}/{self.file_name}",
            user=self.valid_user,
            expected_status=401,
        )

    @pytest.mark.skipif(
        not bucket_name,
        reason="Skipping this test, since a valid s3 bucket name couldn't be found ",
    )
    def test_unauthorized_user_cannot_post_s3_file(self):
        """Unauthorized user should receive 403 when posting a S3 file."""
        self.gen3_workflow.put_bucket_object_with_boto3(
            content="dummy_S3_content",
            object_path=f"{self.bucket_name}/{self.folder_name}/{self.file_name}",
            user=self.invalid_user,
            expected_status=403,
        )

    @pytest.mark.skipif(
        not bucket_name,
        reason="Skipping this test, since a valid s3 bucket name couldn't be found ",
    )
    def test_unauthorized_user_cannot_get_s3_file(self):
        """Unauthorized user should receive 403 when trying to GET a S3 file."""
        self.gen3_workflow.get_bucket_object_with_boto3(
            object_path=f"{self.bucket_name}/{self.folder_name}/{self.file_name}",
            user=self.invalid_user,
            expected_status=403,
        )

    @pytest.mark.skipif(
        not bucket_name,
        reason="Skipping this test, since a valid s3 bucket name couldn't be found ",
    )
    def test_happy_path_upload_and_get_s3_file(self):
        """
        POST an S3 file in a `directoy/filename` format,
        then GET with the `directory/` to test the list-object functionality
        followed by GET `directory/filename`to verify the uploaded file exists.
        """

        input_content = "sample_S3_content"
        self.gen3_workflow.put_bucket_object_with_boto3(
            content=input_content,
            object_path=f"{self.bucket_name}/{self.folder_name}/{self.file_name}",
            user=self.valid_user,
            expected_status=200,
        )

        # Fetch all the contents in the given folder to verify the list-objects functionality
        response_contents = self.gen3_workflow.list_bucket_objects_with_boto3(
            folder_path=f"{self.bucket_name}/{self.folder_name}/",
            user=self.valid_user,
            expected_status=200,
        )
        assert (
            isinstance(response_contents, list) and len(response_contents) > 0
        ), "Expected the function to return a list of at least one item"
        assert (
            "Key" in response_contents[0]
            and response_contents["Key"] == f"{self.folder_name}/{self.file_name}"
        ), "Expected folder integration-tests in the bucket to have file `test-input.txt`"

        # Fetch the exact file to verify the get-object functionality
        response_s3_object = self.gen3_workflow.get_bucket_object_with_boto3(
            object_path=f"{self.bucket_name}/{self.folder_name}/{self.file_name}",
            user=self.valid_user,
            expected_status=200,
        )

        assert (
            input_content in response_s3_object
        ), "Stored and retrieved content should match"

    @pytest.mark.skipif(
        not bucket_name,
        reason="Skipping this test, since a valid s3 bucket name couldn't be found ",
    )
    def test_happy_path_delete_s3_file(self):
        """DELETE a S3 file, then attempt GET to verify it's gone."""
        self.gen3_workflow.delete_bucket_object_with_boto3(
            object_path=f"{self.bucket_name}/{self.folder_name}/{self.file_name}",
            user=self.valid_user,
            expected_status=200,
        )

        # We expect the request to return a response with status 404
        self.gen3_workflow.get_bucket_object_with_boto3(
            object_path=f"{self.bucket_name}/{self.folder_name}/{self.file_name}",
            user=self.valid_user,
            expected_status=404,
        )
