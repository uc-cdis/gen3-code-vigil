import json
import time

import pytest
from services.gen3workflows import Gen3Workflow, WorkflowStorageConfig
from utils import TEST_DATA_PATH_OBJECT, logger


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

    # Ensure the bucket is wiped before running the tests
    gen3_workflow.delete_user_bucket()

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
        ), f"Expected the function to return a list of at least one item but received: {response_contents}"
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
        ), f"Unauthorized users should receive an empty task list.But found {response} instead"

    def test_unauthorized_user_cannot_create_tes_tasks(self):
        """
        Ensure that an unauthorized user cannot create TES tasks.
        Expects: HTTP 401 Unauthorized response.
        """
        # TODO: Work on 401 for user = None, and 403 for user without `create` policy
        response = self.gen3_workflow.create_tes_task(
            user=self.invalid_user,
            expected_status=401,
        )

    def test_happy_path_create_tes_tasks(self):
        """
        Test Case: Verify that an authorized user can successfully create a TES task.
        Expects: HTTP 200 with an 'id' field in the response.
        """
        body = {
            "name": "Hello world",
            "description": "Demonstrates the most basic echo task.",
            "executors": [
                {"image": "alpine", "command": ["echo", "hello beautiful world!"]}
            ],
            "tags": {"user": "bar"},
        }

        create_task_response = self.gen3_workflow.create_tes_task(
            request_body=body,
            user=self.valid_user,
            expected_status=200,
        )
        assert (
            "id" in create_task_response
        ), f"Create tasks response should contain a valid 'id' field. But found {create_task_response} instead"
        task_id = create_task_response["id"]

        """
        Test Case: Verify that an authorized user can list TES tasks.
        Expects: HTTP 200 with a non-empty task list containing the newly created task ID.
        """

        list_tasks_response = self.gen3_workflow.list_tes_tasks(
            user=self.valid_user,
            expected_status=200,
        )
        assert (
            "tasks" in list_tasks_response
            and isinstance(list_tasks_response["tasks"], list)
            and len(list_tasks_response["tasks"]) > 0
        ), f"The List tasks response should contain a non-empty list of tasks. But found {list_tasks_response} instead"

        task_list = list_tasks_response["tasks"]
        assert task_id in (
            task["id"] for task in task_list
        ), "The created task ID should be present in the task list."

        """
        Test Case: Verify that an authorized user can retrieve a TES task by ID.
        Expects: HTTP 200 and an id field.
        """
        get_tasks_response = self.gen3_workflow.get_tes_task(
            task_id=task_id,
            user=self.valid_user,
            expected_status=200,
        )
        assert (
            "state" in get_tasks_response
        ), f"Task state must exist in response. But found {get_tasks_response} instead."

        valid_states = ["QUEUED", "RUNNING", "COMPLETED"]
        assert (
            get_tasks_response["state"] in valid_states
        ), f"Task state must be one of {valid_states} in response. But found {get_tasks_response['state']} instead."

        # Wait for the task to complete (This is a blocking call)
        retying = 0
        max_retries = 10
        while get_tasks_response["state"] != "COMPLETED" and retying < max_retries:
            time.sleep(30)  # sleep for few seconds before checking the status again
            retying += 1
            get_tasks_response = self.gen3_workflow.get_tes_task(
                task_id=task_id,
                user=self.valid_user,
                expected_status=200,
            )
            logger.debug(
                f"Retry count: {retying}, Task state: {get_tasks_response['state']}"
            )
            if get_tasks_response["state"] in ["FAILED", "CANCELED"]:
                assert False, "The TES task was expected to succeed, but it failed."

        assert (
            get_tasks_response["state"] == "COMPLETED"
        ), f"The TES task did not complete within the expected time frame. Task state must be 'COMPLETED'. But found {get_tasks_response['state']} instead."

    def test_happy_path_cancel_tes_tasks(self):
        """
        Verify that an authorized user can cancel a TES task.
        Expects: HTTP 200 and task status changes to 'Cancelled'.
        """
        response = self.gen3_workflow.create_tes_task(
            user=self.valid_user,
            expected_status=200,
        )
        assert (
            "id" in response
        ), f"Response should contain a valid 'id' field. But found {response} instead"
        task_id = response["id"]

        response = self.gen3_workflow.get_tes_task(
            task_id=task_id,
            user=self.valid_user,
            expected_status=200,
        )
        assert (
            "state" in response
        ), f"Response must have `state` field in it. But found {response} instead"

        response = self.gen3_workflow.cancel_tes_task(
            task_id=task_id,
            user=self.valid_user,
            expected_status=200,
        )
        assert "state" in response and response["state"] in [
            "CANCELING",
            "CANCELED",
        ], f"Task state should be 'CANCELING', 'CANCELED' after cancellation. But found {response} instead"
