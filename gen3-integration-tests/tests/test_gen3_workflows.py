import json
import re
import time

import pytest
from services.gen3workflow import Gen3Workflow, WorkflowStorageConfig
from utils import TEST_DATA_PATH_OBJECT, logger


def is_service_missing(service_name: str):
    manifest_path = f"{TEST_DATA_PATH_OBJECT}/configuration/manifest.json"
    with open(manifest_path, "r") as manifest_file:
        manifest_data = json.load(manifest_file)

    logger.info(
        f"Checking if {service_name} is missing in the manifest file: {manifest_path}"
    )
    return service_name not in manifest_data["versions"]


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

    @classmethod
    def setup_class(cls):
        # Ensure the bucket is wiped before running the tests
        cls.gen3_workflow.delete_user_bucket()

        cls.s3_storage_config = WorkflowStorageConfig.from_dict(
            cls.gen3_workflow.get_storage_info(user=cls.valid_user, expected_status=200)
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
            and response_contents[0]["Key"]
            == f"{self.s3_folder_name}/{self.s3_file_name}"
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
            expected_status=204,
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
            request_body={},
            user=self.invalid_user,
            expected_status=403,
        )

    def test_happy_path_create_tes_tasks(self):
        """
        Test Case: Verify that an authorized user can successfully create a TES task.
        Expects: HTTP 200 with an 'id' field in the response.
        """
        echo_message = "hello beautiful world!"
        s3_testDir_path = f"{self.s3_storage_config.bucket_name}/tes-test-dir"

        # Create files to post it to S3
        files_and_contents = {
            "input.txt": "hello beautiful world!",
            "output.txt": "Random output",
            "grep_output.txt": "Random grep_output output",
        }
        for filename, contents in files_and_contents.items():
            self.gen3_workflow.put_bucket_object_with_boto3(
                content=contents,
                object_path=f"{s3_testDir_path}/{filename}",
                s3_storage_config=self.s3_storage_config,
                user=self.valid_user,
                expected_status=200,
            )

        # Create a TES task
        tes_task_request_body = {
            "name": "Hello world with Word Count",
            "description": "Demonstrates the most basic echo task.",
            "inputs": [
                {"url": f"s3://{s3_testDir_path}/input.txt", "path": "/data/input.txt"}
            ],
            "outputs": [
                {
                    "path": "/data/output.txt",
                    "url": f"s3://{s3_testDir_path}/output.txt",
                    "type": "FILE",
                },
                {
                    "path": "/data/grep_output.txt",
                    "url": f"s3://{s3_testDir_path}/grep_output.txt",
                    "type": "FILE",
                },
            ],
            "executors": [
                {
                    "image": "public.ecr.aws/docker/library/alpine:latest",
                    "command": [
                        f"cat /data/input.txt > /data/output.txt && grep hello /data/input.txt > /data/grep_output.txt && echo Done!"
                    ],
                }
            ],
            "tags": {"user": "bar"},
        }
        create_task_response = self.gen3_workflow.create_tes_task(
            request_body=tes_task_request_body,
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

        valid_states = ["QUEUED", "INITIALIZING", "RUNNING", "COMPLETE"]
        assert (
            get_tasks_response["state"] in valid_states
        ), f"Task state must be one of {valid_states} in response. But found {get_tasks_response['state']} instead."

        # Wait for the task to complete (This is a blocking call)
        retrying = 0
        max_retries = 10
        while get_tasks_response["state"] != "COMPLETE" and retrying < max_retries:
            time.sleep(30)  # sleep for few seconds before checking the status again
            retrying += 1
            get_tasks_response = self.gen3_workflow.get_tes_task(
                task_id=task_id,
                user=self.valid_user,
                expected_status=200,
            )
            logger.debug(
                f"Retry count: {retrying}, Task state: {get_tasks_response['state']}"
            )
            if get_tasks_response["state"] in ["FAILED", "EXECUTOR_ERROR", "CANCELED"]:
                assert (
                    False
                ), "The TES task was expected to succeed, but it failed. Response: {get_tasks_response}"

        assert (
            get_tasks_response["state"] == "COMPLETE"
        ), f"The TES task did not complete within the expected time frame. Task state must be 'COMPLETE'. But found {get_tasks_response['state']} instead.  Response: {get_tasks_response}"
        stdout_message_from_response = get_tasks_response["logs"][0]["logs"][0][
            "stdout"
        ].strip()
        assert (
            stdout_message_from_response == "Done!"
        ), f"The TES task did not return the expected output. Expected: {echo_message}, but found {stdout_message_from_response} instead."

        # Do a get request to both the S3 files and compare the output
        output_response = self.gen3_workflow.get_bucket_object_with_boto3(
            object_path=f"{s3_testDir_path}/output.txt",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=200,
        )
        grep_output_response = self.gen3_workflow.get_bucket_object_with_boto3(
            object_path=f"{s3_testDir_path}/grep_output.txt",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=200,
        )

        assert (
            echo_message in output_response
        ), f"The output_response of the tes task did not return the expected output. Expected: {echo_message} to be in output_response, but found {output_response=} instead."

        assert (
            grep_output_response.strip() == echo_message
        ), f"The grep_output_response of the tes task did not return the expected output. Expected: {echo_message}, but found {grep_output_response} instead."

    def test_happy_path_cancel_tes_tasks(self):
        """
        Verify that an authorized user can cancel a TES task.
        Expects: HTTP 200 and task status changes to 'Cancelled'.
        """
        response = self.gen3_workflow.create_tes_task(
            request_body={
                "name": "Hello world",
                "description": "Demonstrates the most basic echo task.",
                "executors": [
                    {
                        "image": "public.ecr.aws/docker/library/alpine:latest",
                        "command": ["echo", "hello beautiful world!"],
                    }
                ],
                "tags": {"user": "bar"},
            },
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

        # Cancel the task
        self.gen3_workflow.cancel_tes_task(
            task_id=task_id,
            user=self.valid_user,
            expected_status=200,
        )

        # Get the task again to check its state
        response = self.gen3_workflow.get_tes_task(
            task_id=task_id,
            user=self.valid_user,
            expected_status=200,
        )

        assert "state" in response and response["state"] in [
            "CANCELING",
            "CANCELED",
        ], f"Task state should be 'CANCELING', 'CANCELED' after cancellation. But found {response} instead"

    def test_nextflow_workflow(self):
        """
        Test Case: Verify that a Nextflow workflow can be executed successfully.
        Expects: HTTP 200 and a valid status.
        """
        workflow_path = "gen3-integration-tests/test_data/gen3_workflow/"
        self.gen3_workflow.run_nextflow_task(
            workflow_path=workflow_path, storage_config=self.s3_storage_config
        )
