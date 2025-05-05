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

    def _nextflow_parse_completed_line(self, log_line):
        """
        Parses a line from the nextflow log that indicates a completed task.
        Extracts: task name, work directory (and protocol), exit code, and status.

        :param str log_line: A line from the Nextflow log file.
        :return: Dictionary with extracted task information.
        :rtype: dict
        """

        task_info = {
            "process_name": "-",
            "workDir": "-",
            "workDirProtocol": "-",
            "exit_code": "-",
            "status": "-",
        }
        log_regex = (
            r"(?P<timestamp>\w{3}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) .*?"
            r"Task completed > TaskHandler\[.*?"
            r"name: (?P<name>.+); status: (?P<status>-?\w+); "
            r"exit: (?P<exit_code>-?\d+); "
            r".*?workDir: (?P<workDirProtocol>.+):\/\/(?P<workDir>.+)]"
        )
        match = re.match(log_regex, log_line)

        if match:
            task_info["process_name"] = match.group("name")
            task_info["workDir"] = match.group("workDir")
            task_info["workDirProtocol"] = match.group("workDirProtocol")
            task_info["exit_code"] = match.group("exit_code")
            task_info["status"] = match.group("status") or "-"

            if task_info["exit_code"] != "0":
                task_info["status"] = "FAILED"

        return task_info

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

        tasks = response.get("tasks", None)
        assert tasks == [], f"Expected an empty task list, but got: {tasks}"

    def test_unauthorized_user_cannot_create_tes_tasks(self):
        """
        Ensure that an unauthorized user cannot create TES tasks.
        Expects: HTTP 403 Forbidden response.
        """

        self.gen3_workflow.create_tes_task(
            request_body={},
            user=self.invalid_user,
            expected_status=403,
        )

    def test_happy_path_create_tes_tasks(self):
        """
        Test Case: Happy Path for TES Task Creation
        - Upload input file to S3
        - Submit TES task
        - Verify task creation, listing, retrieval, and completion
        - Validate outputs and logs
        """
        message = "hello beautiful world!"
        s3_path_prefix = f"{self.s3_storage_config.bucket_name}/tes-test-dir"

        # Step 1: Upload input file to S3
        self.gen3_workflow.put_bucket_object_with_boto3(
            content=message,
            object_path=f"{s3_path_prefix}/input.txt",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=200,
        )

        # Step 2: Create a TES task
        tes_task_payload = {
            "name": "Hello world with Word Count",
            "description": "Demonstrates the most basic echo task.",
            "inputs": [
                {"url": f"s3://{s3_path_prefix}/input.txt", "path": "/data/input.txt"}
            ],
            "outputs": [
                {
                    "path": "/data/output.txt",
                    "url": f"s3://{s3_path_prefix}/output.txt",
                    "type": "FILE",
                },
                {
                    "path": "/data/grep_output.txt",
                    "url": f"s3://{s3_path_prefix}/grep_output.txt",
                    "type": "FILE",
                },
            ],
            "executors": [
                {
                    "image": "public.ecr.aws/docker/library/alpine:latest",
                    "command": [
                        "cat /data/input.txt > /data/output.txt && grep hello /data/input.txt > /data/grep_output.txt && echo Done!"
                    ],
                }
            ],
            "tags": {"user": self.valid_user},
        }
        task_response = self.gen3_workflow.create_tes_task(
            request_body=tes_task_payload,
            user=self.valid_user,
            expected_status=200,
        )

        task_id = task_response.get("id", None)
        assert task_id, f"Expected 'id' in response, but got: {task_response}"

        # Step 3: Verify task is listed
        list_tes_tasks_response = self.gen3_workflow.list_tes_tasks(
            user=self.valid_user,
            expected_status=200,
        )

        tasks_list = list_tes_tasks_response.get("tasks", [])
        assert tasks_list, f"Expected non-empty list but got: {tasks_list}"

        assert any(
            task["id"] == task_id for task in tasks_list
        ), "The created task ID should be present in the task list."

        # Step 4: Poll until the TES task completes or fails with a known status
        max_retries = 10
        poll_interval = 30  # seconds
        transient_states = {"QUEUED", "INITIALIZING", "RUNNING"}
        final_success_state = "COMPLETE"
        final_failure_states = {"FAILED", "EXECUTOR_ERROR", "CANCELED"}

        for attempt in range(1, max_retries + 1):
            task_info = self.gen3_workflow.get_tes_task(
                task_id=task_id,
                user=self.valid_user,
                expected_status=200,
            )
            state = task_info.get("state")

            if state == final_success_state:
                break
            elif state in final_failure_states:
                assert (
                    False
                ), f"TES task failed. Final state: {state}, Response: {task_info}"
            elif state not in transient_states:
                assert (
                    False
                ), f"Unexpected TES task state '{state}' encountered. Response: {task_info}"

            logger.debug(f"Attempt {attempt}: Task state is '{state}', retrying...")
            time.sleep(poll_interval)
        else:
            assert (
                False
            ), f"TES task did not complete in time. Final state: {state}, Response: {task_info}"

        # Step 5: Validate task logs
        stdout = task_info["logs"][0]["logs"][0]["stdout"].strip()
        assert (
            stdout == "Done!"
        ), f"Expected stdout to be `Done!`, but found {stdout} instead."

        # Step 6: Validate task outputs
        s3_contents = {
            file_name: self.gen3_workflow.get_bucket_object_with_boto3(
                object_path=f"{s3_path_prefix}/{file_name}",
                s3_storage_config=self.s3_storage_config,
                user=self.valid_user,
                expected_status=200,
            )
            for file_name in ["output.txt", "grep_output.txt"]
        }

        assert (
            message in s3_contents["output.txt"]
        ), f"The output_response of the tes task did not return the expected output. Expected: {message} to be in output_response, but found {s3_contents['output.txt']} instead."

        assert (
            s3_contents["grep_output.txt"].strip() == message
        ), f"The grep_output_response of the tes task did not return the expected output. Expected: {message}, but found {s3_contents['grep_output.txt'].strip()} instead."

    def test_happy_path_cancel_tes_tasks(self):
        """
        Verify that an authorized user can cancel a TES task.
        Expects: HTTP 200 and task status changes to 'Cancelled'.
        """
        payload = {
            "name": "Hello world",
            "description": "Demonstrates the most basic echo task.",
            "executors": [
                {
                    "image": "public.ecr.aws/docker/library/alpine:latest",
                    "command": ["echo", "hello beautiful world!"],
                }
            ],
            "tags": {"user": "bar"},
        }
        # Step 1: Create a TES task
        task_info = self.gen3_workflow.create_tes_task(
            request_body=payload,
            user=self.valid_user,
            expected_status=200,
        )
        task_id = task_info.get("id", None)
        assert task_id, f"Expected 'id' in response, but got: {task_info}"

        # Step 2: Retrieve the task to check its state
        task_info = self.gen3_workflow.get_tes_task(
            task_id=task_id,
            user=self.valid_user,
            expected_status=200,
        )

        assert (
            "state" in task_info
        ), f"Response must have `state` field in it. But found {task_info} instead"

        # Step 3: Cancel the TES task
        self.gen3_workflow.cancel_tes_task(
            task_id=task_id,
            user=self.valid_user,
            expected_status=200,
        )

        # Step 4: Verify the task is cancelled
        task_info = self.gen3_workflow.get_tes_task(
            task_id=task_id,
            user=self.valid_user,
            expected_status=200,
        )

        final_state = task_info.get("state", None)
        valid_states = {"CANCELING", "CANCELED"}
        assert (
            final_state in valid_states
        ), f"Task state should be one of {valid_states} after cancellation. But found {final_state} instead. Task Info: {task_info}"

    def test_nextflow_workflow(self):
        """
        Test Case: Verify that a Nextflow workflow can be executed successfully.
        """
        expected_task_outputs = {
            "extract_metadata (1)": {
                "filename": "dicom-metadata-img-1.dcm.csv",
                "command": "python3 /utils/extract_metadata.py img-1.dcm",
            },
            "extract_metadata (2)": {
                "filename": "dicom-metadata-img-2.dcm.csv",
                "command": "python3 /utils/extract_metadata.py img-2.dcm",
            },
            "dicom_to_png (1)": {
                "filename": "img-1.png",
                "command": "python3 /utils/dicom_to_png.py img-1.dcm",
            },
            "dicom_to_png (2)": {
                "filename": "img-2.png",
                "command": "python3 /utils/dicom_to_png.py img-2.dcm",
            },
        }
        workflow_dir = "test_data/gen3_workflow/"
        workflow_log = self.gen3_workflow.run_nextflow_task(
            workflow_dir=workflow_dir,
            workflow_script="main.nf",
            nextflow_config_file="nextflow.config",
        )

        completed_tasks = [
            self._nextflow_parse_completed_line(line)
            for line in workflow_log.split("\n")
            if "Task completed > TaskHandler" in line
        ]

        for task in completed_tasks:

            task_name = task["process_name"]
            assert (
                task_name in expected_task_outputs
            ), f"Unexpected task name: {task_name}. Expected one of {list(expected_task_outputs.keys())}"

            expected = expected_task_outputs[task_name]

            assert (
                task["status"] == "COMPLETED"
            ), f"Task {task_name} failed with status: {task['status']}"
            assert (
                task["exit_code"] == "0"
            ), f"Task {task_name} failed with exit code: {task['exit_code']}"
            assert (
                task["workDirProtocol"] == "s3"
            ), f"Expected workDir to be an 's3' location, but got {task['workDirProtocol']}"

            s3_file_list = self.gen3_workflow.list_bucket_objects_with_boto3(
                folder_path=task["workDir"],
                s3_storage_config=self.s3_storage_config,
                user=self.valid_user,
            )

            assert (
                s3_file_list
            ), f"Expected to find files in the S3 bucket for task {task_name}, but got an empty list"

            filenames_in_s3 = {file["Key"].split("/")[-1] for file in s3_file_list}

            assert (
                expected["filename"] in filenames_in_s3
            ), f"Expected to find {expected['filename']} in the S3 bucket for task {task_name}, but got {s3_file_list}"

            command_file_keys = [
                file["Key"]
                for file in s3_file_list
                if file["Key"].endswith(".command.sh")
            ]
            assert (
                len(command_file_keys) == 1
            ), f"Expected to find exactly one .command.sh file for task {task_name}, but got {len(command_file_keys)}. Files: {command_file_keys}"

            command_file_key = command_file_keys[0]

            # get contents of .command.sh file
            command_script_contents = self.gen3_workflow.get_bucket_object_with_boto3(
                object_path=f"{self.s3_storage_config.bucket_name}/{command_file_key}",
                s3_storage_config=self.s3_storage_config,
                user=self.valid_user,
            )

            assert (
                expected["command"] in command_script_contents
            ), f"Expected to find `{expected['command']}` in the .command.sh file for task {task_name}, but got {command_script_contents}"


# TODO: Add more tests for the following:
# 1. Test the POST /ga4gh/tes/v1/tasks/ endpoint with a command that fails. (e.g. `exit 1` and `cd <missing_directory>`)
# 2. Test the POST /ga4gh/tes/v1/tasks/ endpoint with an invalid command format (e.g. cmd = ['False'] key)
