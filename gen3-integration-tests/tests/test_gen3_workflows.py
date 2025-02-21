import json

import pytest
from services.gen3workflows import Gen3Workflow, WorkflowStorageConfig
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
    s3_folder_name = "integration-tests"
    s3_file_name = "test-input.txt"
    s3_storage_config = WorkflowStorageConfig.from_dict(
        gen3_workflow.get_storage_info(user=valid_user, expected_status=200)
    )

    ######################## Test /storage/info endpoint ########################

    def test_get_storage_info_without_token(self):
        """Test GET /storage/info without an access token."""
        self.gen3_workflow.get_storage_info(user=None, expected_status=401)

    ######################## Test /s3/ endpoint ########################

    def test_any_user_cannot_get_s3_file_with_unsigned_request(self):
        """Unsigned requests should receive 401 even if the user is authorized to get data."""
        self.gen3_workflow.get_bucket_object_with_unsigned_request(
            object_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/{self.s3_file_name}",
            user=self.valid_user,
            expected_status=401,
        )

    def test_unauthorized_user_cannot_post_s3_file(self):
        """Unauthorized user should receive 403 when posting a S3 file."""
        self.gen3_workflow.put_bucket_object_with_boto3(
            content="dummy_S3_content",
            object_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/{self.s3_file_name}",
            s3_storage_config=self.s3_storage_config,
            user=self.invalid_user,
            expected_status=403,
        )

    def test_unauthorized_user_cannot_get_s3_file(self):
        """Unauthorized user should receive 403 when trying to GET a S3 file."""
        self.gen3_workflow.get_bucket_object_with_boto3(
            object_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/{self.s3_file_name}",
            s3_storage_config=self.s3_storage_config,
            user=self.invalid_user,
            expected_status=403,
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
            object_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/{self.s3_file_name}",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=200,
        )

        # Fetch all the contents in the given folder to verify the list-objects functionality
        response_contents = self.gen3_workflow.list_bucket_objects_with_boto3(
            folder_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=200,
        )
        assert (
            isinstance(response_contents, list) and len(response_contents) > 0
        ), "Expected the function to return a list of at least one item but received: {response_contents}"
        assert (
            "Key" in response_contents[0]
            and response_contents["Key"] == f"{self.s3_folder_name}/{self.s3_file_name}"
        ), f"Expected folder {self.s3_folder_name} in the bucket to have file `{self.s3_file_name}` but received {response_contents}"

        # Fetch the exact file to verify the get-object functionality
        response_s3_object = self.gen3_workflow.get_bucket_object_with_boto3(
            object_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/{self.s3_file_name}",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=200,
        )

        assert (
            input_content in response_s3_object
        ), "Stored and retrieved content should match"

    def test_happy_path_delete_s3_file(self):
        """
        POST an S3 file in a `directoy/filename` format,
        then, DELETE the S3 file,
        then attempt GET to verify it's gone.
        """
        input_content = "sample_S3_content"
        self.gen3_workflow.put_bucket_object_with_boto3(
            content=input_content,
            object_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/{self.s3_file_name}",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=200,
        )

        self.gen3_workflow.delete_bucket_object_with_boto3(
            object_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/{self.s3_file_name}",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=200,
        )

        # We expect the request to return a response with status 404
        self.gen3_workflow.get_bucket_object_with_boto3(
            object_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/{self.s3_file_name}",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=404,
        )

    ######################## Test /ga4gh/tes/v1/tasks endpoint ########################

    def test_unauthorized_user_cannot_list_tes_tasks(self):
        """
        Ensure that an unauthorized user cannot list TES tasks.
        Expects: HTTP 200 with an empty task list in the response.
        """
        response = self.gen3_workflow.list_tes_tasks(
            user=self.invalid_user,
            expected_status=200,
        )
        assert (
            "tasks" in response
            and isinstance(response["tasks"], list)
            and len(response["tasks"]) == 0
        ), "Unauthorized users should receive an empty task list."

    def test_unauthorized_user_cannot_create_tes_tasks(self):
        """
        Ensure that an unauthorized user cannot create TES tasks.
        Expects: HTTP 401 Unauthorized response.
        """
        response = self.gen3_workflow.create_tes_task(
            user=self.invalid_user,
            expected_status=401,
        )

    def test_happy_path_create_tes_tasks(self):
        """
        Verify that an authorized user can successfully create a TES task.
        Expects: HTTP 200 with an 'id' field in the response.
        """
        response = self.gen3_workflow.create_tes_task(
            user=self.valid_user,
            expected_status=200,
        )
        assert "id" in response, "Response should contain a valid 'id' field."

    def test_happy_path_list_tes_tasks(self):
        """
        Verify that an authorized user can list TES tasks.
        Expects: HTTP 200 with a non-empty task list containing the newly created task ID.
        """
        response = self.gen3_workflow.create_tes_task(
            user=self.valid_user,
            expected_status=200,
        )
        assert "id" in response, "Response should contain a valid 'id' field."
        task_id = response["id"]

        response = self.gen3_workflow.list_tes_tasks(
            user=self.valid_user,
            expected_status=200,
        )
        assert (
            "tasks" in response
            and isinstance(response["tasks"], list)
            and len(response["tasks"]) > 0
        ), "The response should contain a non-empty list of tasks."

        task_list = response["tasks"]
        assert task_id in (
            task["id"] for task in task_list
        ), "The created task ID should be present in the task list."

    def test_happy_path_get_tes_tasks(self):
        """
        Verify that an authorized user can retrieve a TES task by ID.
        Expects: HTTP 200 with a valid status field ('Queued', 'Running', or 'Completed'). #TODO: Verify if the values in the status field are accurate
        """
        response = self.gen3_workflow.create_tes_task(
            user=self.valid_user,
            expected_status=200,
        )
        assert "id" in response, "Response should contain a valid 'id' field."
        task_id = response["id"]

        response = self.gen3_workflow.get_tes_task(
            task_id=task_id,
            user=self.valid_user,
            expected_status=200,
        )
        assert "status" in response and response["status"] in [
            "Queued",
            "Running",
            "Completed",
        ], "Task status should be 'Queued', 'Running', or 'Completed'."

    def test_happy_path_cancel_tes_tasks(self):
        """
        Verify that an authorized user can cancel a TES task.
        Expects: HTTP 200 and task status changes to 'Cancelled'.
        """
        response = self.gen3_workflow.create_tes_task(
            user=self.valid_user,
            expected_status=200,
        )
        assert "id" in response, "Response should contain a valid 'id' field."
        task_id = response["id"]

        response = self.gen3_workflow.get_tes_task(
            task_id=task_id,
            user=self.valid_user,
            expected_status=200,
        )
        assert "status" in response and response["status"] in [
            "Queued",
            "Running",
            "Completed",
        ], "Task status should be 'Queued', 'Running', or 'Completed'."

        response = self.gen3_workflow.cancel_tes_task(
            task_id=task_id,
            user=self.valid_user,
            expected_status=200,
        )
        assert (
            "status" in response and response["status"] == "Cancelled"
        ), "Task status should be 'Cancelled' after cancellation."
