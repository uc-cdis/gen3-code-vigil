"""
The `TestGen3Workflow` class includes common setup and test selecting flags.
The other classes inherit from the `TestGen3Workflow` class and run the actual tests.

Not fixed yet:
- #38 (KMS encryption fails when using `executors.stdout`)
- #57, #69, #71, #80 Maybe add a Funnel reconciler test: check that old resources are being cleared
- #62 (task volumes): check the created executor pod similarly to what is done in `test_request_cpu`
- #73 (job retries must not swallow executor or worker error logs)
- #75, #81 (useful executor pod events in task logs)
- #76 (no SYSTEM_ERROR on missing output file)
- #85 (space in output file name)
- #86 (list tasks with a tag filter, list all tasks with a user that has extra access)
- Support large files and long workflows. Includes #83. May need to be a nightly build test if it
  takes too long, but then it won't be tested by the Kind CI used in the Funnel repos.

As of this writing, the last issue was #87. Any newer issues may require additional tests.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time

import jwt
import pytest
from boto3.s3.transfer import TransferConfig
from dateutil import parser
from services.gen3workflow import Gen3Workflow, WorkflowStorageConfig
from services.requestor import Requestor
from utils import logger


def _nextflow_parse_completed_line(log_line):
    """
    Parses a line from the nextflow log that indicates a completed task.
    Extracts: task name, work directory (and protocol), exit code, and status.

    :param str log_line: A line from the Nextflow log file.
    :return: Dictionary with extracted task information.
    :rtype: dict

    Example log line:
    "Jun-03 12:10:57.578 [Task monitor] .. Task completed > TaskHandler[id: 2; name: extract_metadata (1); status: COMPLETED; exit: 0; error: -; workDir: s3://bucket-name/work-dir]"
    Example return value:
    {
        "process_name": "extract_metadata (1)",
        "workDir": "bucket-name/work-dir",
        "workDirProtocol": "s3",
        "exit_code": "0",
        "status": "COMPLETED"
    }
    """

    task_info = {
        "process_name": "-",
        "workDir": "-",
        "workDirProtocol": "-",
        "exit_code": "-",
        "status": "-",
        "timestamp": "-",
    }
    log_regex = (
        r"(?P<timestamp>\w{3}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) .*?"
        r"Task completed > TaskHandler\[.*?"
        r"name: (?P<name>.+); status: (?P<status>-?\w+); "
        r"exit: (?P<exit_code>-?\d+); "
        r".*?workDir: (?P<workDirProtocol>.+:\/\/)?(?P<workDir>.+)]"
    )

    match = re.match(log_regex, log_line)

    if match:
        task_info["process_name"] = match.group("name")
        task_info["workDir"] = match.group("workDir")
        task_info["workDirProtocol"] = match.group("workDirProtocol")
        task_info["exit_code"] = match.group("exit_code")
        task_info["status"] = match.group("status") or "-"
        task_info["timestamp"] = match.group("timestamp")

        if task_info["workDirProtocol"]:
            task_info["workDirProtocol"] = task_info["workDirProtocol"].split("://")[0]

    return task_info


def _nextflow_parse_completed_tasks(completed_tasks):
    """
    Input: list of completed tasks, as produced by `_nextflow_parse_completed_line`.
    Output: dictionary of completed task name to the task's latest run, since tasks may be
    retried in case of failure.
    """
    res = {}
    for task in completed_tasks:
        if task["process_name"] not in res:
            res[task["process_name"]] = task
            continue
        new_timestamp = parser.parse(task["timestamp"])
        stored_timestamp = parser.parse(res[task["process_name"]]["timestamp"])
        logger.info(
            f"'{task['process_name']}' ran more than once. Keeping the latest run. Timestamps: {stored_timestamp} and {new_timestamp}"
        )
        if new_timestamp > stored_timestamp:
            res[task["process_name"]] = task
    return res


@pytest.mark.skipif(
    "funnel" not in pytest.deployed_services,
    reason="funnel service is not running on this environment",
)
@pytest.mark.skipif(
    "gen3-workflow" not in pytest.deployed_services,
    reason="gen3-workflow service is not running on this environment",
)
@pytest.mark.gen3_workflow
class TestGen3Workflow(object):
    @classmethod
    def setup_class(cls):
        cls.gen3_workflow = Gen3Workflow()
        cls.valid_user = "main_account"
        cls.other_valid_user = "user0_account"
        cls.invalid_user = "dummy_one"
        cls.s3_folder_name = "integration-tests"
        cls.s3_file_name = "test-input.txt"

        # Hit the storage setup endpoint for all users who will be creating tasks.
        cls.s3_storage_config = WorkflowStorageConfig.from_dict(
            cls.gen3_workflow.setup_storage(user=cls.valid_user, expected_status=200)
        )
        cls.gen3_workflow.setup_storage(user=cls.other_valid_user, expected_status=200)

        # Ensure the bucket is emptied before running the tests (must run after
        # `storage_setup` so the user has access to empty the bucket)
        cls.gen3_workflow.cleanup_user_bucket()
        cls.gen3_workflow.cleanup_user_bucket(user=cls.other_valid_user)


class TestGen3WorkflowService(TestGen3Workflow):
    def test_setup_storage_unauthorized(self):
        """Test GET /storage/setup without an access token or with an unauthorized token."""
        self.gen3_workflow.setup_storage(user=None, expected_status=401)
        self.gen3_workflow.setup_storage(user=self.invalid_user, expected_status=403)

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

        Regression test for TES issues:
        - #40 (support Nextflow "publishDir" directive): copy functionality
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
        assert any(
            e.get("Key") == f"{self.s3_folder_name}/{self.s3_file_name}"
            for e in response_contents
        ), f"Expected bucket folder `{self.s3_folder_name}` to have file `{self.s3_file_name}` but received {response_contents}"

        # Fetch the exact file to verify the get-object functionality
        response_s3_object = self.gen3_workflow.get_bucket_object_with_boto3(
            object_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/{self.s3_file_name}",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=200,
        )
        response_contents = response_s3_object["Body"].read().decode("utf-8")
        assert (
            input_content == response_contents
        ), "Stored and retrieved content should match"

        # Test the Copy functionality: copy the file from an S3 location to another
        self.gen3_workflow._perform_s3_action(
            "copy",
            object_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/{self.s3_file_name}",
            dest_object_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/{self.s3_file_name}_copied",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=None,
        )
        response_s3_object = self.gen3_workflow.get_bucket_object_with_boto3(
            object_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/{self.s3_file_name}_copied",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=200,
        )
        response_contents = response_s3_object["Body"].read().decode("utf-8")
        assert (
            input_content == response_contents
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

    def test_multipart_upload(self):
        # Create a 6MB file (multipart can only be used for files >=5MB) and upload it
        input_content = b"A" * (6 * 1024 * 1024)
        with tempfile.NamedTemporaryFile(delete=True) as file_to_upload:
            file_to_upload.write(input_content)
            file_to_upload.flush()
            self.gen3_workflow._perform_s3_action(
                "upload_file",
                filename=file_to_upload.name,
                object_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/{self.s3_file_name}",
                s3_storage_config=self.s3_storage_config,
                expected_status=None,  # boto3 `upload_file` returns None, so expect None response
                config=TransferConfig(multipart_threshold=1),  # force multipart
            )

        # Test the Copy functionality: copy the file from an S3 location to another
        self.gen3_workflow._perform_s3_action(
            "copy",
            object_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/{self.s3_file_name}",
            dest_object_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/{self.s3_file_name}_copied",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=None,
            config=TransferConfig(multipart_threshold=1),  # force multipart
        )

        # Check the contents of the 2nd file to verify that both the upload and the copy succeeded
        response_s3_object = self.gen3_workflow.get_bucket_object_with_boto3(
            object_path=f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}/{self.s3_file_name}_copied",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=200,
        )
        response_contents = response_s3_object["Body"].read().decode("utf-8")
        assert (
            input_content.decode() == response_contents
        ), "Stored and retrieved content should match"


class TestGen3WorkflowTES(TestGen3Workflow):
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

    def test_unauthorized_user_cannot_create_tes_task(self):
        """
        Ensure that an unauthorized user cannot create TES task.
        Expects: HTTP 403 Forbidden response.
        """

        self.gen3_workflow.create_tes_task(
            request_body={},
            user=self.invalid_user,
            expected_status=403,
        )

    @pytest.mark.parametrize("with_input_output", [True, False])
    def test_happy_path_create_tes_task(self, with_input_output):
        """
        Test Case: Happy Path for TES Task Creation
        - Upload input file to S3
        - Submit TES task
        - Verify task creation, listing, retrieval, and completion
        - Validate outputs and logs

        Regression test for TES issues:
        - #8 (create a task without input)
        - #20 (ability to list tasks)
        - #48-a (no "Operation not permitted" on output files that require `incremental-upload` on PV)
        - #48-b (successful task returns an exit code)
        """
        # Step 1: Upload input file to S3
        if with_input_output:
            input_file_contents = "hello beautiful world!"
            s3_path_prefix = (
                f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}"
            )
            self.gen3_workflow.put_bucket_object_with_boto3(
                content=input_file_contents,
                object_path=f"{s3_path_prefix}/input.txt",
                s3_storage_config=self.s3_storage_config,
                user=self.valid_user,
                expected_status=200,
            )

        # Step 2: Create a TES task
        echo_message = "done!"
        if with_input_output:
            tes_task_payload = {
                "name": "Hello world with Word Count",
                "description": "Demonstrates the most basic echo task.",
                "inputs": [
                    {
                        "url": f"s3://{s3_path_prefix}/input.txt",
                        "path": "/work/input.txt",
                    }
                ],
                "outputs": [
                    {
                        "path": "/work/output.txt",
                        "url": f"s3://{s3_path_prefix}/output.txt",
                        "type": "FILE",
                    },
                    {
                        "path": "/work/grep_output.txt",
                        "url": f"s3://{s3_path_prefix}/grep_output.txt",
                        "type": "FILE",
                    },
                ],
                "executors": [
                    {
                        "image": "public.ecr.aws/docker/library/alpine:latest",
                        "workdir": "/work",
                        "command": [
                            f"touch output.txt && cat input.txt > output.txt && grep hello input.txt > grep_output.txt && echo {echo_message}",
                        ],
                    }
                ],
            }
        else:
            tes_task_payload = {
                "name": "Hello world without input/output",
                "description": "Demonstrates the most basic echo task.",
                "executors": [
                    {
                        "image": "public.ecr.aws/docker/library/alpine:latest",
                        "command": [f"echo {echo_message}"],
                    }
                ],
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
        task_info = self.gen3_workflow.poll_until_task_reaches_expected_state(
            task_id=task_id,
            user=self.valid_user,
            expected_final_state="COMPLETE",
        )

        # Step 5: Validate task logs
        task_logs = task_info.get("logs", [])
        assert (
            len(task_logs) > 0 and len(task_logs[0].get("logs", [])) > 0
        ), f"Expected task logs to be present and have at least one log entry, but got: {task_logs}"
        assert (
            "stdout" in task_logs[0]["logs"][0]
        ), f"Expected task log entry to have 'stdout', but got: {task_logs[0]['logs'][0]}"

        # Check if the stdout contains the expected echo message
        stdout = task_logs[0]["logs"][0]["stdout"].strip()
        assert (
            stdout == echo_message
        ), f"Expected stdout to be `{echo_message}`, but found `{stdout}` instead."

        exit_code = task_logs[0]["logs"][0].get("exit_code")
        assert (
            exit_code == 0
        ), f"Expected successful task's exit code to be 0, but got {exit_code}"

        # Step 6: Validate task outputs
        if not with_input_output:
            return
        for file_name in ["output.txt", "grep_output.txt"]:
            response = self.gen3_workflow.get_bucket_object_with_boto3(
                object_path=f"{s3_path_prefix}/{file_name}",
                s3_storage_config=self.s3_storage_config,
                user=self.valid_user,
                expected_status=200,
            )

            try:
                output_file_contents = response["Body"].read().decode("utf-8").strip()
            except Exception as e:
                logger.error(
                    f"Failed to read or decode content of {file_name} from S3. Error: {e}"
                )
                raise

            assert (
                input_file_contents == output_file_contents
            ), f"File '{file_name}' does not have the expected contents. Expected: '{input_file_contents}', but found '{output_file_contents}'."

    def test_happy_path_cancel_tes_task(self):
        """
        Verify that an authorized user can cancel a TES task.
        Expects: HTTP 200 and task status changes to 'Cancelled'.

        Also verify that attempting to cancel a task that is already canceled does not return an
        error.

        Regression test for TES issues:
        - #74 (successful task cancelation)
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
        }
        # Step 1: Create a TES task
        task_info = self.gen3_workflow.create_tes_task(
            request_body=payload,
            user=self.valid_user,
            expected_status=200,
        )
        task_id = task_info.get("id", None)
        assert task_id, f"Expected 'id' in response, but got: {task_info}"

        # Step 2: Cancel the TES task
        response = self.gen3_workflow.cancel_tes_task(
            task_id=task_id,
            user=self.valid_user,
            expected_status=200,
        )
        assert response == {}

        # Step 3: Verify the task is cancelled
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

        # Step 4: Attempt to cancel the TES task again
        response = self.gen3_workflow.cancel_tes_task(
            task_id=task_id,
            user=self.valid_user,
            expected_status=200,
        )
        assert response == {
            "message": "Task is already in CANCELED state, no action needed"
        }

    def test_task_that_does_not_exist(self):
        """
        Regression test for TES issues:
        - #25 (gracefully handle canceling a task that does not exist)
        - #26 (gracefully handle getting a task that does not exist)
        """
        self.gen3_workflow.get_tes_task(
            task_id="does-not-exist",
            user=self.valid_user,
            expected_status=404,
        )

        self.gen3_workflow.cancel_tes_task(
            task_id="does-not-exist",
            user=self.valid_user,
            expected_status=404,
        )

    # FIXME: This test is currently not relying on networkpolicies to restrict access to internal endpoints,
    #  To test the access restriction accurately, we need to run `curl http://arborist-service.<namespace>/user`
    #  More info: https://ctds-planx.atlassian.net/browse/MIDRC-1227
    @pytest.mark.skip(reason="test needs to be updated")
    def test_access_internal_endpoints(self):
        """
        Test Case: Access internal endpoints must be restricted
        - Create and submit a TES task where we try to curl into arborist service
        - Make a GET call with the task ID to verify that the task failed
        """

        # Step 1: Create a TES task where we try to curl into arborist service
        tes_task_payload = {
            "name": "Hello world after hitting arborist",
            "description": "Tries to reach arborist-service before saying HelloWorld!",
            "executors": [
                {
                    "image": "quay.io/curl/curl:latest",
                    "command": [
                        # Known Funnel issue (#38): tasks are failing too early, which causes worker pods to remain stuck in the RUNNING state.
                        # Adding a temporary `sleep(10)` as a workaround to unblock the test until the underlying issue is fixed.
                        "sleep 10 && curl http://arborist-service/user"
                    ],
                }
            ],
        }
        task_response = self.gen3_workflow.create_tes_task(
            request_body=tes_task_payload,
            user=self.valid_user,
            expected_status=200,
        )

        task_id = task_response.get("id", None)
        assert task_id, f"Expected 'id' in response, but got: {task_response}"

        # Step 2: Poll until the TES task completes or fails with a known status
        task_info = self.gen3_workflow.poll_until_task_reaches_expected_state(
            task_id=task_id, user=self.valid_user, expected_final_state="EXECUTOR_ERROR"
        )

        # FIXME: Ideally even if the test fails with an EXEC_ERROR we must be able to see the
        # task_logs, but we currently see None. Need to investigate further, once fixed
        # Uncomment the following code.

        # task_logs = task_info.get("logs", [])
        # stdout = task_logs[0]["logs"][0]["stdout"].strip() if len(task_logs) > 0 else ""
        # assert (
        #     "Could not resolve host: arborist-service" in stdout
        # ), "Expected output to have an error message indicating arborist service connection failure, but found {stdout} instead"

    @pytest.mark.parametrize(
        "test_case",
        [
            {
                "command": ["echo 'This will fail' && exit 123"],
                "expected_exit_code": 123,  # This is to ensure response's error code matches the executor command's exit code
                "expected_state": "EXECUTOR_ERROR",
                "expected_logs": "This will fail\n",
            },
            {
                "command": ["False"],
                "expected_exit_code": 127,  # command not found
                "expected_state": "EXECUTOR_ERROR",
                "expected_logs": "/bin/sh: False: not found\n",
            },
            {
                "command": ["cd missing/directory"],
                "expected_exit_code": 2,
                "expected_state": "EXECUTOR_ERROR",
                "expected_logs": "/bin/sh: cd: line 0: can't cd to missing/directory: No such file or directory\n",
            },
        ],
    )
    def test_command_failure_in_tes_task(self, test_case):
        """
        Test Case: Verify that a TES task with a failing command is marked as failed and logs are captured.
        - Create a TES task with a command from the test case
        - Poll until the task fails
        - Verify the exit code and that the task status is 'EXECUTOR_ERROR' (if the provided command returns a non-0 exit code) or 'SYSTEM_ERROR' (if the provided task cannot be run)
        - Validate that the logs capture the error message

        Regression test for TES issues:
        - #2 (task that completes with an error must not be reported successful)
        - #38 (task with failing command must not stay stuck in "Running" state)
        """

        # Step 1: Create a TES task
        tes_task_payload = {
            "name": f"Task with failing command: {test_case['command']}",
            "description": f"This task is expected to fail due to a non-zero exit code: {test_case['command']}",
            "executors": [
                {
                    "image": "public.ecr.aws/docker/library/alpine:latest",
                    "command": test_case["command"],
                }
            ],
        }
        task_response = self.gen3_workflow.create_tes_task(
            request_body=tes_task_payload,
            user=self.valid_user,
            expected_status=200,
        )

        task_id = task_response.get("id", None)
        assert task_id, f"Expected 'id' in response, but got: {task_response}"

        # Step 2: Poll until the TES task fails with a known status
        task_info = self.gen3_workflow.poll_until_task_reaches_expected_state(
            task_id=task_id,
            user=self.valid_user,
            expected_final_state=test_case["expected_state"],
        )

        task_exit_code = None
        task_logs = task_info.get("logs", [])
        if task_logs and len(task_logs) > 0 and len(task_logs[0].get("logs", [])) > 0:
            task_exit_code = task_logs[0]["logs"][0].get("exit_code")
            executor_logs = task_logs[0]["logs"][0].get("stdout")

        assert (
            task_exit_code == test_case["expected_exit_code"]
        ), f"Expected exit code to be {test_case['expected_exit_code']}, but found {task_exit_code} instead. Response: {json.dumps(task_info, indent=2)}"

        assert (
            executor_logs == test_case["expected_logs"]
        ), f"Expected logs to be '{test_case['expected_logs']}', but found '{executor_logs}' instead. Response: {json.dumps(task_info, indent=2)}"

    def test_multi_user_task_isolation(self):
        """
        Test Case: Verify that users can only see and access their own TES tasks and storage,
        unless they are granted explicit access.
        - User A creates a TES task and uploads a file to S3
        - User B attempts to access User A's TES task and S3 file, and is denied access
        - User C has access to User A's tasks, but not to their storage (that is not currently
          supported by gen3-workflow)

        Regression test for TES issues:
        - #31 (first user B creates task B, then user A creates task A: task A must belong to
          user A == files in user A's bucket)
        """
        user_A = self.valid_user
        user_B = self.other_valid_user
        user_C = "user1_account"

        # User B creates a TES task
        task_response = self.gen3_workflow.create_tes_task(
            request_body={
                "name": "User B's Task",
                "executors": [
                    {
                        "image": "public.ecr.aws/docker/library/alpine:latest",
                        "command": ["echo", "Hello from User B!"],
                    }
                ],
            },
            user=user_B,
            expected_status=200,
        )
        task_id = task_response.get("id", None)
        assert task_id, f"Expected 'id' in response, but got: {task_response}"

        # User B can access their own task, and user A fails to access User B's task
        self.gen3_workflow.get_tes_task(
            task_id=task_id,
            user=user_B,
            expected_status=200,
        )
        self.gen3_workflow.get_tes_task(
            task_id=task_id,
            user=user_A,
            expected_status=403,
        )

        # User A creates a TES task
        s3_path_prefix = f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}"
        task_response = self.gen3_workflow.create_tes_task(
            request_body={
                "name": "User A's Task",
                "executors": [
                    {
                        "image": "public.ecr.aws/docker/library/alpine:latest",
                        "command": [
                            "touch",
                            "/work/output.txt",
                            "&&",
                            "echo",
                            "Hello from User A!",
                        ],
                    }
                ],
                "outputs": [
                    {
                        "path": "/work/output.txt",
                        "url": f"s3://{s3_path_prefix}/output.txt",
                        "type": "FILE",
                    },
                ],
            },
            user=user_A,
            expected_status=200,
        )
        task_id = task_response.get("id", None)
        assert task_id, f"Expected 'id' in response, but got: {task_response}"

        # User A can access their own task, and user B fails to access User A's task
        self.gen3_workflow.get_tes_task(
            task_id=task_id,
            user=user_A,
            expected_status=200,
        )
        self.gen3_workflow.get_tes_task(
            task_id=task_id,
            user=user_B,
            expected_status=403,
        )

        if "requestor" in pytest.deployed_services:
            # Grant user C access to user A's tasks (not through the user.yaml because the resource
            # path must include user A's ID, which is not guaranteed to be the same in all CI runs)
            logger.info(
                f"Requestor is deployed: granting {pytest.users[user_C]} access to {pytest.users[user_A]}'s tasks"
            )
            requestor = Requestor()
            user_A_id = jwt.decode(
                self.gen3_workflow._get_access_token(user_A),
                algorithms=["RS256"],
                options={"verify_signature": False},
            )["sub"]
            resource_path = f"/services/workflow/gen3-workflow/tasks/{user_A_id}"
            resp = requestor.create_request_with_auth_header(
                username=pytest.users[user_C],
                resource_paths=[resource_path],
                role_ids=["gen3_workflow_reader"],
                request_status="SIGNED",
            )
            assert (
                resp.status_code == 201
            ), f"Unable to grant {pytest.users[user_C]} access to {resource_path}"
        else:
            # in the gen3-workflow Kind CI, Requestor is not deployed but user A always has the
            # same user ID, so access is granted through the user.yaml
            logger.info(
                f"Requestor not is deployed: assuming {pytest.users[user_C]} already has access to {pytest.users[user_A]}'s tasks"
            )
        self.gen3_workflow.get_tes_task(
            task_id=task_id,
            user=user_C,
            expected_status=200,
        )

        # Poll until the TES task completes
        self.gen3_workflow.poll_until_task_reaches_expected_state(
            task_id=task_id,
            user=self.valid_user,
            expected_final_state="COMPLETE",
        )

        # Check that the output file is in the right user's bucket
        bucket_contents = self.gen3_workflow.list_bucket_objects_with_boto3(
            folder_path=f"{self.s3_storage_config.bucket_name}/funnel-temp-files/{task_id}/",
            s3_storage_config=self.s3_storage_config,
            user=user_A,
            expected_status=200,
        )
        assert bucket_contents and len(bucket_contents) >= 1
        assert bucket_contents[0]["Key"].endswith("/output.txt")

        # User A uploads a file to S3
        s3_path_prefix = f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}"
        self.gen3_workflow.put_bucket_object_with_boto3(
            content="User A's secret data",
            object_path=f"{s3_path_prefix}/user_a_file.txt",
            s3_storage_config=self.s3_storage_config,
            user=user_A,
            expected_status=200,
        )

        # User A can access their own S3 file, and user B fails to access User A's S3 file
        self.gen3_workflow.get_bucket_object_with_boto3(
            object_path=f"{s3_path_prefix}/user_a_file.txt",
            s3_storage_config=self.s3_storage_config,
            user=user_A,
            expected_status=200,
        )
        self.gen3_workflow.get_bucket_object_with_boto3(
            object_path=f"{s3_path_prefix}/user_a_file.txt",
            s3_storage_config=self.s3_storage_config,
            user=user_B,
            expected_status=403,
        )

    @pytest.mark.parametrize(
        "invalid_payload",
        [
            {
                # Missing required 'executors' field
                "name": "Invalid Task 1",
                "description": "This task is missing the 'executors' field.",
            },
            {
                "name": "Invalid Task 2",
                "description": "This task has an invalid command format.",
                "executors": [
                    {
                        "image": "public.ecr.aws/docker/library/alpine:latest",
                        # Invalid command format (should be a list of strings)
                        "command": "not_a_list",
                    }
                ],
            },
        ],
    )
    def test_create_task_format_error(self, invalid_payload):
        """
        Test Case: Verify that creating a TES task with an invalid request format returns a 400 error.
        - Attempt to create a TES task with missing required fields and invalid command format
        - Verify that the response status is 400 Bad Request

        Note: These tests are a part of integration tests instead of unit tests, because the error
        is thrown by funnel and not gen3-workflow, and we want to verify that the error is properly
        propagated through gen3-workflow's API.

        Regression test for TES issues:
        - #3, #14, #29 (failed task creation request must not return a successful response)
          Note that not all edge cases can be tested: this was usually triggered by kubernetes job
          creation bugs which are now fixed.
        - #42 (gracefully handle invalid command format)
        """

        self.gen3_workflow.create_tes_task(
            request_body=invalid_payload,
            user=self.valid_user,
            expected_status=400,
        )

    @pytest.mark.parametrize(
        "echo_message, expected_stdout",
        [
            pytest.param(
                "I'm done!",
                "'I'm done!'",
                id="quote",
            ),
            pytest.param(
                "hello/world,please/ignore,goodbye/world",
                "hello/world,please/ignore,goodbye/world",
                id="comma",
            ),
        ],
    )
    def test_command_with_special_char(self, echo_message, expected_stdout):
        """
        This is a regression test for an issue when the command contains quotes:
        `Error: yaml: line 33: did not find expected ',' or ']'`
        or `/bin/sh: syntax error: unterminated quoted string`.

        A current limitation of quote handling is that the command received by the Funnel executor
        is: echo \'I\'m done!\' so the output includes extra quotes (see `expected_stdout`
        variable).

        Regression test for TES issues:
        - #12, #41 (quotes in command)
        - #59 (comma in command)
        """
        tes_task_payload = {
            "name": "Task with special char",
            "executors": [
                {
                    "image": "public.ecr.aws/docker/library/alpine:latest",
                    "command": [f"echo '{echo_message}'"],
                }
            ],
        }
        task_response = self.gen3_workflow.create_tes_task(
            request_body=tes_task_payload,
            user=self.valid_user,
            expected_status=200,
        )
        task_id = task_response.get("id", None)
        assert task_id, f"Expected 'id' in response, but got: {task_response}"

        # Poll until the TES task completes or fails with a known status
        task_info = self.gen3_workflow.poll_until_task_reaches_expected_state(
            task_id=task_id,
            user=self.valid_user,
            expected_final_state="COMPLETE",
        )

        # Check if the stdout contains the expected echo message
        task_logs = task_info.get("logs", [])
        assert (
            len(task_logs) > 0 and len(task_logs[0].get("logs", [])) > 0
        ), f"Expected task logs to be present and have at least one log entry, but got: {task_logs}"
        assert (
            "stdout" in task_logs[0]["logs"][0]
        ), f"Expected task log entry to have 'stdout', but got: {task_logs[0]['logs'][0]}"
        stdout = task_logs[0]["logs"][0]["stdout"].strip()
        assert (
            stdout == expected_stdout
        ), f"Expected stdout to be `{expected_stdout}`, but found `{stdout}` instead."

    @pytest.mark.parametrize(
        "requests", [{"cpu": 1, "mem": 2, "disk": 3}, {"cpu": 3, "mem": 1, "disk": 2}]
    )
    def test_request_cpu(self, requests):
        """
        Verify that the resources requested in the TES task body are indeed what the executor
        container requests.

        Regression test for TES issues:
        - #43 (request a specific number of CPUs)
        """

        # Create a TES task
        tes_task_payload = {
            "name": "Request and check CPUs",
            "resources": {
                "cpu_cores": requests["cpu"],
                "ram_gb": requests["mem"],
                "disk_gb": requests["disk"],
            },
            "executors": [
                {
                    "image": "public.ecr.aws/docker/library/alpine:latest",
                    # sleep for long enough to describe the pod once it's running
                    "command": ["sleep 60"],
                }
            ],
        }
        task_response = self.gen3_workflow.create_tes_task(
            request_body=tes_task_payload,
            user=self.valid_user,
            expected_status=200,
        )
        task_id = task_response.get("id", None)
        assert task_id, f"Expected 'id' in response, but got: {task_response}"

        # Poll until the task starts running so we know the worker pod has started
        self.gen3_workflow.poll_until_task_reaches_expected_state(
            task_id=task_id,
            user=self.valid_user,
            expected_final_state="RUNNING",
        )

        # Wait until the executor has started to get its requested CPU, memory and storage
        # TODO: Funnel release rc-37 adds a taskId label to all the executor pods: use it to filter
        cmd = [
            f'kubectl get pod -l app=funnel-executor -n workflow-pods-{pytest.namespace} -o custom-columns="NAME:.metadata.name,REQUESTS:.spec.containers[*].resources.requests" | grep {task_id}'
        ]
        max_retries = 10
        container_requests = ""
        for attempt in range(1, max_retries + 1):
            result = subprocess.run(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            if result.returncode == 0:
                container_requests = (
                    result.stdout.decode("utf-8").split("map")[-1].strip()
                )
            else:
                raise Exception(
                    f"Failed to run command '{cmd}' (code {result.returncode}): {result.stderr.decode('utf-8')}"
                )
            if container_requests:
                break
            if attempt <= max_retries:
                time.sleep(10)
        if not container_requests:
            raise Exception(
                f"TES executor for task '{task_id}' was not created in time"
            )

        assert (
            container_requests
            == f"[cpu:{requests['cpu']} ephemeral-storage:{requests['disk']}Gi memory:{requests['mem']}Gi]"
        ), f"Expected the container to request '{requests}', but the requests are '{container_requests}'"

        # Note: no need to wait for the task to finish running in this case

    def test_no_secrets_in_logs(self):
        """
        Verify no secrets are being dumped in the Funnel or Funnel worker logs.

        Regression test for TES issues:
        - #44 (secrets must not be logged when the config is logged)
        """

        # Look for 3 secret values: Funnel DB password, Funnel OIDC client secret, and
        # "GenericS3.Key" value set by the Funnel plugin (in the format "<token>;userId=<user_id>")
        secrets = {"GenericS3.Key": ";userId="}
        for secret_name, field in [
            ("funnel-dbcreds", "password"),
            ("funnel-oidc-client", "client_secret"),
        ]:
            cmd = [
                f"kubectl -n {pytest.namespace} get secret {secret_name} -o jsonpath='{{.data.{field}}}' | base64 --decode"
            ]
            logger.info(f"Running command: {cmd}")
            result = subprocess.run(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            if result.returncode == 0:
                secret_val = result.stdout.decode("utf-8").strip()
                assert (
                    secret_val
                ), f"Unable to get value for secret '{secret_name}.{field}'"
                secrets[f"{secret_name}.{field}"] = secret_val
            else:
                raise Exception(
                    f"Failed to run command '{cmd}' (code {result.returncode}): {result.stderr.decode('utf-8')}"
                )

        # Create a TES task
        tes_task_payload = {
            "name": "Request and check CPUs",
            "executors": [
                {
                    "image": "public.ecr.aws/docker/library/alpine:latest",
                    "command": ["sleep 60"],  # sleep for long enough to get the logs
                }
            ],
        }
        task_response = self.gen3_workflow.create_tes_task(
            request_body=tes_task_payload,
            user=self.valid_user,
            expected_status=200,
        )
        task_id = task_response.get("id", None)
        assert task_id, f"Expected 'id' in response, but got: {task_response}"

        # Poll until the task starts running so we know the worker pod has started
        self.gen3_workflow.poll_until_task_reaches_expected_state(
            task_id=task_id,
            user=self.valid_user,
            expected_final_state="RUNNING",
        )

        # Get the Funnel logs
        cmd = [
            f"kubectl -n {pytest.namespace} logs -l app=funnel --all-containers --tail -1"
        ]
        result = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if result.returncode == 0:
            funnel_logs = result.stdout.decode("utf-8")
        else:
            raise Exception(
                f"Failed to run command '{cmd}' (code {result.returncode}): {result.stderr.decode('utf-8')}"
            )

        # Get the Funnel worker logs
        cmd = [
            f"kubectl -n workflow-pods-{pytest.namespace} logs -l app=funnel-worker --all-containers --tail -1"
        ]
        result = subprocess.run(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if result.returncode == 0:
            worker_logs = result.stdout.decode("utf-8")
        else:
            raise Exception(
                f"Failed to run command '{cmd}' (code {result.returncode}): {result.stderr.decode('utf-8')}"
            )

        for logs_name, logs in [
            ("funnel server", funnel_logs),
            ("funnel worker", worker_logs),
        ]:
            for secret_name, secret_val in secrets.items():
                assert (
                    secret_val not in logs
                ), f"Found secret '{secret_name}' ('{secret_val}') in {logs_name} logs: {logs}"

        # Note: no need to wait for the task to finish running in this case

    def test_task_with_environment_variable(self):
        """
        Regression test for TES issues:
        - #61 (set specified env vars)
        """
        tes_task_payload = {
            "name": "Env var test",
            "executors": [
                {
                    "image": "public.ecr.aws/docker/library/alpine:latest",
                    "command": ["env"],
                    "env": {
                        "SOMETHING": "VALUE",
                    },
                }
            ],
        }
        task_response = self.gen3_workflow.create_tes_task(
            request_body=tes_task_payload,
            user=self.valid_user,
            expected_status=200,
        )
        task_id = task_response.get("id", None)
        assert task_id, f"Expected 'id' in response, but got: {task_response}"

        # Poll until the TES task completes
        task_info = self.gen3_workflow.poll_until_task_reaches_expected_state(
            task_id=task_id,
            user=self.valid_user,
            expected_final_state="COMPLETE",
        )

        # Check if the stdout contains the expected echo message
        task_logs = task_info.get("logs", [])
        assert (
            len(task_logs) > 0 and len(task_logs[0].get("logs", [])) > 0
        ), f"Expected task logs to be present and have at least one log entry, but got: {task_logs}"
        assert (
            "stdout" in task_logs[0]["logs"][0]
        ), f"Expected task log entry to have 'stdout', but got: {task_logs[0]['logs'][0]}"
        stdout = task_logs[0]["logs"][0]["stdout"].strip()
        assert (
            "SOMETHING=VALUE" in stdout
        ), f"Expected env var to be set, but `env` returned: {stdout}"


class TestGen3WorkflowNextflow(TestGen3Workflow):
    """
    Nextflow tests are currently broken in the Kind CI.

    - Nextflow logs:
    nextflow.exception.AbortOperationException: Cannot create work-dir 's3://gen3wf-localhost-1/ga4gh-tes' -- Make sure you have write permissions or specify a different directory by using the `-w` command line option

    - gen3-workflow logs:
    Incoming S3 request from user '1': 'PUT gen3wf-localhost-1/ga4gh-tes/'
    Outgoing S3 request: 'PUT http://minio.gen3-code-vigil-pr-561.svc.cluster.local:9000/gen3wf-localhost-1/ga4gh-tes/'
    Error from S3: 403 <?xml version="1.0" encoding="UTF-8"?>
    2026-06-01T23:00:33.9689129Z <Error><Code>SignatureDoesNotMatch</Code><Message>The request signature we calculated does not match the signature you provided. Check your key and signing method.</Message><Key>ga4gh-tes/</Key><BucketName>gen3wf-localhost-1</BucketName><Resource>/gen3wf-localhost-1/ga4gh-tes/</Resource><RequestId>18B5174696300C46</RequestId><HostId>dd9025bab4ad464b049177c95eb6ebf374d3b3fd1af9251148b658df7ac2e3e8</HostId></Error>
    "PUT /s3/gen3wf-localhost-1/ga4gh-tes/ HTTP/1.0" 403
    """

    def test_nextflow_workflow(self):
        """
        Test Case: Verify that a Nextflow workflow can be executed successfully.

        Regression test for TES issues:
        - #5 (output a whole directory)
        - #35 (missing stdout)
        - #72 (missing command.out/.log/.err files)
        """
        expected_task_outputs = {
            "extract_metadata": {
                "filenames": {
                    "dicom-metadata-img-1.dcm.csv",
                    "dicom-metadata-img-2.dcm.csv",
                },
                "command": "python3 /utils/extract_metadata.py img-ID_PLACEHOLDER.dcm",
            },
            "dicom_to_png": {
                "filenames": {"img-1.png", "img-2.png"},
                "command": "python3 /utils/dicom_to_png.py img-ID_PLACEHOLDER.dcm\nmkdir outputs\ncp *.png outputs/",
            },
        }
        workflow_dir = "test_data/gen3_workflow/"
        workflow_log = self.gen3_workflow.run_nextflow_workflow(
            workflow_dir=workflow_dir,
            workflow_script="main.nf",
            nextflow_config_file="nextflow.config",
            s3_working_directory=self.s3_storage_config.working_directory,
        )
        logger.info(f"Workflow log:")
        completed_tasks = []
        for line in workflow_log.splitlines():
            logger.info(line)
            if "Task completed > TaskHandler" in line:
                completed_tasks.append(_nextflow_parse_completed_line(line))

        for task_name, task in _nextflow_parse_completed_tasks(completed_tasks).items():
            task_category = task_name.split(" ")[0]
            assert (
                task_category in expected_task_outputs
            ), f"Unexpected task name: {task_name}. Expected one of {list(expected_task_outputs.keys())}"
            expected_task_outputs[task_category]["ran"] = True

            assert task["workDir"].startswith(
                f"{self.s3_storage_config.bucket_name}/"
            ), f"[{task_name}] Expected workDir to begin with bucket name -- {self.s3_storage_config.bucket_name}, but got {task['workDir']}"

            expected = expected_task_outputs[task_category]

            assert (
                task["status"] == "COMPLETED"
            ), f"Task '{task_name}' failed with status: {task['status']}"
            assert (
                task["exit_code"] == "0"
            ), f"Task '{task_name}' returned exit code {task['exit_code']}"
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
            ), f"Expected to find files in the S3 bucket for task '{task_name}', but got an empty list"

            filenames_in_s3 = {file["Key"].split("/")[-1] for file in s3_file_list}

            overlapped_filenames = expected["filenames"] & filenames_in_s3
            assert (
                overlapped_filenames and len(overlapped_filenames) == 1
            ), f"Expected to find exactly one of '{expected['filenames']}' to be present in the S3 bucket for task '{task_name}', but found files {s3_file_list}"
            # Unpacking the single overlapped filename from the set
            (expected_file,) = overlapped_filenames
            if "dicom_to_png" in task_name:
                expected_file = f"/outputs/{expected_file}"

            # Verify the expected file is non-empty
            response = self.gen3_workflow.get_bucket_object_with_boto3(
                object_path=f"{task['workDir']}/{expected_file}",
                s3_storage_config=self.s3_storage_config,
                user=self.valid_user,
            )
            assert (
                response["ContentLength"] > 0
            ), f"Expected to have some data in {expected_file}. But found empty file instead. Response: {response}"

            def get_nextflow_output_file_contents(test_file_name):
                matching_keys = [
                    file["Key"]
                    for file in s3_file_list
                    if file["Key"].endswith(test_file_name)
                ]
                assert (
                    len(matching_keys) == 1
                ), f"[{task_name}] Expected to find exactly one {test_file_name} file', but got {len(matching_keys)}. Files: {matching_keys}"

                s3_key = matching_keys[0]

                # get contents of file
                response = self.gen3_workflow.get_bucket_object_with_boto3(
                    object_path=f"{self.s3_storage_config.bucket_name}/{s3_key}",
                    s3_storage_config=self.s3_storage_config,
                    user=self.valid_user,
                )

                try:
                    return response["Body"].read().decode("utf-8")
                except Exception as e:
                    logger.error(
                        f"[{task_name}] Failed to read or decode content of {s3_key} from S3. Error: {e}"
                    )
                    raise

            test_files = [
                "/.command.sh",
                "/.exitcode",
                "/.command.out",
                "/.command.log",
            ]
            for test_file_name in test_files:
                file_contents = get_nextflow_output_file_contents(test_file_name)

                if test_file_name == "/.command.sh":
                    # Replace placeholders in the expected command with the actual filename
                    # identified for the task.
                    file_num = "1" if "1" in expected_file else "2"
                    expected_command_with_filename = expected["command"].replace(
                        "ID_PLACEHOLDER", file_num
                    )
                    expected_file_contents = (
                        f"#!/bin/bash -ue\n{expected_command_with_filename}\n"
                    )
                elif test_file_name == "/.exitcode":
                    expected_file_contents = "0"
                    if expected_file_contents != file_contents:
                        # when the task failed, log the contents of the error output file for
                        # debugging purposes
                        err_file_contents = get_nextflow_output_file_contents(
                            "/.command.err"
                        )
                        logger.info(
                            f"[{task_name}] /.command.err contents:\n{err_file_contents}"
                        )
                elif test_file_name == "/.command.out":
                    expected_file_contents = ""
                elif test_file_name in ["/.command.log", "/.command.err"]:
                    if "dicom_to_png" in task_name:
                        expected_file_contents = ""
                    else:  # `extract_metadata` task_name
                        # This task currently outputs task progress and a warning (`A value is
                        # trying to be set on a copy of a slice from a DataFrame`).
                        # We do not check the full logs, just that the file is not empty.
                        assert (
                            file_contents
                        ), f"[{task_name}] {test_file_name} file is unexpectedly empty"
                        continue

                assert expected_file_contents == file_contents, {
                    f"[{task_name}] {test_file_name} file does not contain the expected data.\n"
                    f"Expected to find: `{expected_file_contents}`\n"
                    f"Actual content: `{file_contents}`"
                }

        for task_category in expected_task_outputs.keys():
            assert (
                expected_task_outputs[task_category].get("ran") == True
            ), f"Expected to see completed '{task_category}' tasks"

    @pytest.mark.parametrize(
        "run_gpu_test",
        [
            False,
            pytest.param(
                True,
                marks=pytest.mark.skipif(
                    "localhost" in pytest.hostname,
                    reason="GPU tasks are not supported by the Kind CI",
                ),
            ),
        ],
    )
    def test_nf_canary(self, run_gpu_test):
        """
        Run the Nextflow infrastructure tests from https://github.com/seqeralabs/nf-canary

        Currently skipping tests that are known to be unsupported in our environment:
        - TEST_MV_FILE and TEST_MV_FOLDER_CONTENTS. Error:
            mv: cannot move 'test.txt' to 'output.txt': Operation not permitted
            -- they are not supported by S3 CSI mount (https://github.com/awslabs/mountpoint-s3/issues/506#issuecomment-1709952359)

        Regression test for TES issues:
        - #40 (support Nextflow "publishDir" directive)
        - #60 (dynamic NodeSelector and Toleration configs to support GPU tasks)
        """
        known_unsupported = ["TEST_MV_FILE", "TEST_MV_FOLDER_CONTENTS"]

        # clone the tests repo
        directory = "test_data/gen3_workflow/nf-canary"
        shutil.rmtree(directory, ignore_errors=True)
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "https://github.com/seqeralabs/nf-canary.git",
                directory,
            ]
        )

        if run_gpu_test:
            # only run the GPU test
            params = {"gpu": "true", "run": "TEST_GPU"}

            # ask the server to schedule on a GPU node
            config_lines = ["tes.tags._GPU = 'yes'"]

            # the test requests 10G memory, but our configured limit is 4G: override to 1G
            with open(f"{directory}/main.nf", "r") as file:
                data = file.read()
            with open(f"{directory}/main.nf", "w") as file:
                file.write(data.replace("memory '10G'", "memory '1G'"))
        else:
            # do not run unsupported tests or the GPU test (no `gpu` param)
            params = {"skip": ",".join(known_unsupported)}
            config_lines = []

        # update the nextflow config
        config_lines += [
            "process.executor = 'tes'",
            "process.time = '20 min'",
            # for some reason using `plugins.id` here throws `UnsupportedOperationException`
            "plugins {id 'nf-ga4gh'}",
            "tes.endpoint = \"${env('HOSTNAME_PROTOCOL')}://${env('HOSTNAME')}/ga4gh/tes\"",
            "tes.oauthToken = env('GEN3_TOKEN')",
            "tes.timeout = 120",
            "aws.accessKey = env('GEN3_TOKEN')",
            "aws.secretKey = 'N/A'",
            f"aws.region = '{self.s3_storage_config.bucket_region}'",
            "aws.client.endpoint = \"${env('HOSTNAME_PROTOCOL')}://${env('HOSTNAME')}/workflows/s3\"",
            "aws.client.s3PathStyleAccess = true",
            "aws.client.maxErrorRetry = 1",
            "workDir = env('WORK_DIR')",
            # this test tends to fail intermittently; improve stability with retries for now:
            "process.errorStrategy = 'retry'",
            "process.maxRetries = 2",
        ]
        with open(os.path.join(directory, "nextflow.config"), "a") as file:
            file.write("\n".join(config_lines) + "\n")

        # run the test nextflow workflow
        workflow_log = self.gen3_workflow.run_nextflow_workflow(
            workflow_dir=directory,
            workflow_script="main.nf",
            nextflow_config_file="nextflow.config",
            s3_working_directory=self.s3_storage_config.working_directory,
            params=params,
        )

        # check that each test == each task succeeded
        logger.info(f"Workflow log:")
        completed_tasks = []
        tasks_with_ignored_error = []
        for line in workflow_log.splitlines():
            logger.info(line)
            if "Task completed > TaskHandler" in line:
                completed_tasks.append(_nextflow_parse_completed_line(line))
            if "Error is ignored" in line:
                try:
                    # Example line: Jan-29 18:12:33.445 [TaskFinalizer-6] INFO  nextflow.processor.
                    # TaskProcessor - [13/6084d3] NOTE: Process `NF_CANARY:TEST_IGNORED_FAIL (1)`
                    # terminated with an error exit status (1) -- Error is ignored
                    task_name = line.split("NF_CANARY:")[1].split(" ")[0]
                    tasks_with_ignored_error.append(task_name)
                except IndexError:
                    logger.error(
                        f"Unable to extract task name from log line. Proceeding... Log line: {line}"
                    )
        assert len(completed_tasks) > 0

        logger.info("Completed tasks:")
        logger.info(json.dumps(completed_tasks, indent=2))

        for task_name, task in _nextflow_parse_completed_tasks(completed_tasks).items():
            assert (
                task["status"] == "COMPLETED"
            ), f"Task '{task_name}' failed with status: {task['status']}"
            assert (
                # Note: code `1` is not in the TES spec but is currently returned by Funnel in case
                # of error
                task["exit_code"]
                == ("1" if "TEST_IGNORED_FAIL" in task_name else "0")
            ), f"Task '{task_name}' returned exit code {task['exit_code']}"

        assert (
            tasks_with_ignored_error == [] if run_gpu_test else ["TEST_IGNORED_FAIL"]
        ), "TEST_IGNORED_FAIL failure is expected to be ignored"
