import json
import os
import re
import shutil
import subprocess
import time

import pytest
from services.gen3workflow import Gen3Workflow, WorkflowStorageConfig
from utils import logger
from utils.misc import retry


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

        if task_info["workDirProtocol"]:
            task_info["workDirProtocol"] = task_info["workDirProtocol"].split("://")[0]

    return task_info


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

        cls.s3_storage_config = WorkflowStorageConfig.from_dict(
            cls.gen3_workflow.setup_storage(user=cls.valid_user, expected_status=200)
        )

        # Ensure the bucket is emptied before running the tests (must run after
        # `storage_setup` so the user has access to empty the bucket)
        cls.gen3_workflow.cleanup_user_bucket()

    ######################## Test /storage/setup endpoint ########################

    def test_setup_storage_without_token(self):
        """Test GET /storage/setup without an access token."""
        self.gen3_workflow.setup_storage(user=None, expected_status=401)

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
        response_contents = response_s3_object["Body"].read().decode("utf-8")
        assert (
            input_content in response_contents
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

    def test_happy_path_create_tes_task(self):
        """
        Test Case: Happy Path for TES Task Creation
        - Upload input file to S3
        - Submit TES task
        - Verify task creation, listing, retrieval, and completion
        - Validate outputs and logs
        """
        input_file_contents = "hello beautiful world!"
        s3_path_prefix = f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}"

        # Step 1: Upload input file to S3
        self.gen3_workflow.put_bucket_object_with_boto3(
            content=input_file_contents,
            object_path=f"{s3_path_prefix}/input.txt",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=200,
        )

        # Step 2: Create a TES task
        echo_message = "I'm done!"
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
                        # Note: This also serves as a regression test for an issue when the command contains quotes:
                        # `Error: yaml: line 33: did not find expected ',' or ']'`
                        # A current limitation of quote handling is that the command received by
                        # the Funnel executor is: echo \'I\'m done!\'
                        # so the output includes extra quotes (see `expected_stdout` variable).
                        f"cat /data/input.txt > /data/output.txt && grep hello /data/input.txt > /data/grep_output.txt && echo '{echo_message}'",
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
        expected_stdout = f"'{echo_message}'"
        assert (
            stdout == expected_stdout
        ), f"Expected stdout to be `{expected_stdout}`, but found `{stdout}` instead."

        # Step 6: Validate task outputs
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

        # Step 2: Cancel the TES task
        self.gen3_workflow.cancel_tes_task(
            task_id=task_id,
            user=self.valid_user,
            expected_status=200,
        )

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

    def test_nextflow_workflow(self):
        """
        Test Case: Verify that a Nextflow workflow can be executed successfully.
        """
        expected_task_outputs = {
            "extract_metadata": {
                "filenames": {
                    "dicom-metadata-img-1.dcm.csv",
                    "dicom-metadata-img-2.dcm.csv",
                },
                "command": "python3 /utils/extract_metadata.py img-*.dcm",
            },
            "dicom_to_png": {
                "filenames": {"img-1.png", "img-2.png"},
                "command": "python3 /utils/dicom_to_png.py img-*.dcm",
            },
        }
        workflow_dir = "test_data/gen3_workflow/"
        workflow_log = self.gen3_workflow.run_nextflow_task(
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

        for task in completed_tasks:

            task_name = task["process_name"]
            task_category = task["process_name"].split(" ")[0]
            assert (
                task_category in expected_task_outputs
            ), f"Unexpected task name: {task_name}. Expected one of {list(expected_task_outputs.keys())}"

            assert task["workDir"].startswith(
                f"{self.s3_storage_config.bucket_name}/"
            ), f"[{task_name}] Expected workDir to begin with bucket name -- {self.s3_storage_config.bucket_name}, but got {task['workDir']}"

            expected = expected_task_outputs[task_category]

            assert (
                task["status"] == "COMPLETED"
            ), f"Task '{task_name}' failed with status: {task['status']}"
            assert (
                task["exit_code"] == "0"
            ), f"Task '{task_name}' failed with exit code: {task['exit_code']}"
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
                    # Replace the 'img-*.dcm' in the expected command with the actual filename identified for the task.
                    file_num = "1" if "1" in expected_file else "2"
                    expected_command_with_filename = expected["command"].replace(
                        "*", file_num
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
                    else:  # extract_metadata task_name
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

    def test_nf_canary(self):
        """
        Run the Nextflow infrastructure tests from https://github.com/seqeralabs/nf-canary

        TODO (MIDRC-1203): fix infra to support the following tests:
        - TEST_MV_FILE and TEST_MV_FOLDER_CONTENTS. Error:
            mv: cannot move 'test.txt' to 'output.txt': Operation not permitted
        - TEST_PUBLISH_FILE and TEST_PUBLISH_FOLDER. Error:
            Failed to publish file: s3://gen3wf-pauline-planx-pla-net-16/ga4gh-tes/33/
            ab32810279415c8067b64a73518812/test; to: s3://gen3wf-pauline-planx-pla-net-16/ga4gh-tes/
            outputs/test [copy] -- attempt: 1; reason: Failed to parse XML document with handler
            class com.amazonaws.services.s3.model.transform.
        - TEST_GPU (only runs with param `gpu: true`). Reported successful but fails with:
            CUDA is not available on this system.
            [...]
            in gpu_computation
              x = torch.rand(size, size, device='cuda')
            RuntimeError: Found no NVIDIA driver on your system. Please check that you have an
            NVIDIA GPU and installed a driver from http://www.nvidia.com/Download/index.aspx
        - TEST_FUSION_DOCTOR: unknown cause
        """
        known_unsupported = [
            "TEST_MV_FILE",
            "TEST_MV_FOLDER_CONTENTS",
            "TEST_GPU",
            "TEST_FUSION_DOCTOR",
        ]

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

        # update the nextflow config
        lines = [
            "process.executor = 'tes'",
            # for some reason using `plugins.id` here throws `UnsupportedOperationException`
            "plugins {id 'nf-ga4gh'}",
            'tes.endpoint = "https://${HOSTNAME}/ga4gh/tes"',
            'tes.oauthToken = "${GEN3_TOKEN}"',
            'aws.accessKey = "${GEN3_TOKEN}"',
            "aws.secretKey = 'N/A'",
            f"aws.region = '{self.s3_storage_config.bucket_region}'",
            'aws.client.endpoint = "https://${HOSTNAME}/workflows/s3"',
            "aws.client.s3PathStyleAccess = true",
            "aws.client.maxErrorRetry = 1",
            'workDir = "${WORK_DIR}"',
            # this test tends to fail intermittently; improve stability with retries for now:
            "process.errorStrategy = 'retry'",
            "process.maxRetries = 2",
        ]
        with open(os.path.join(directory, "nextflow.config"), "a") as file:
            file.write("\n".join(lines) + "\n")

        # run the test nextflow workflow
        workflow_log = self.gen3_workflow.run_nextflow_task(
            workflow_dir=directory,
            workflow_script="main.nf",
            nextflow_config_file="nextflow.config",
            s3_working_directory=self.s3_storage_config.working_directory,
            params={"gpu": "true", "skip": ",".join(known_unsupported)},
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

        for task in completed_tasks:
            task_name = task["process_name"]
            assert (
                task["status"] == "COMPLETED"
            ), f"Task '{task_name}' failed with status: {task['status']}"
            assert (
                # Note: code `1` is not in the TES spec but is currently returned by Funnel in case
                # of error
                task["exit_code"]
                == ("1" if "TEST_IGNORED_FAIL" in task_name else "0")
            ), f"Task '{task_name}' failed with exit code: {task['exit_code']}"

        assert tasks_with_ignored_error == [
            "TEST_IGNORED_FAIL"
        ], "TEST_IGNORED_FAIL failure is expected to be ignored"

    # FIXME: This test is currently not relying on networkpolicies to restrict access to internal endpoints,
    #  To test the access restriction accurately, we need to run `curl http://arborist-service.<namespace>/user`
    #  More info: https://ctds-planx.atlassian.net/browse/MIDRC-1227
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
                    "image": "curlimages/curl:latest",
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
            },
            {
                "command": ["False"],
                "expected_exit_code": 0,  # This is current funnel's behavior issue #53
                "expected_state": "SYSTEM_ERROR",
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
            "tags": {"user": self.valid_user},
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

        assert (
            task_exit_code == test_case["expected_exit_code"]
        ), f"Expected exit code to be {test_case['expected_exit_code']}, but found {task_exit_code} instead. Response: {task_info}"

    def test_multi_user_task_isolation(self):
        """
        Test Case: Verify that users can only see and access their own TES tasks and storage.
        - User A creates a TES task and uploads a file to S3
        - User B attempts to access User A's TES task and S3 file, and is denied access
        """

        # Step 1: User A creates a TES task
        tes_task_payload = {
            "name": "User A's Task",
            "description": "This task belongs to User A.",
            "executors": [
                {
                    "image": "public.ecr.aws/docker/library/alpine:latest",
                    "command": ["echo", "Hello from User A!"],
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

        # Step 2: User B attempts to access User A's TES task
        self.gen3_workflow.get_tes_task(
            task_id=task_id,
            user=self.other_valid_user,
            expected_status=403,
        )
        # Verify that User A can access their own task
        self.gen3_workflow.get_tes_task(
            task_id=task_id,
            user=self.valid_user,
            expected_status=200,
        )

        # Step 3: User A uploads a file to S3
        s3_path_prefix = f"{self.s3_storage_config.bucket_name}/{self.s3_folder_name}"
        self.gen3_workflow.put_bucket_object_with_boto3(
            content="User A's secret data",
            object_path=f"{s3_path_prefix}/user_a_file.txt",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=200,
        )

        # Step 4: User B attempts to access User A's S3 file
        self.gen3_workflow.get_bucket_object_with_boto3(
            object_path=f"{s3_path_prefix}/user_a_file.txt",
            s3_storage_config=self.s3_storage_config,
            user=self.other_valid_user,
            expected_status=403,
        )

        # Verify that User A can access their own S3 file
        self.gen3_workflow.get_bucket_object_with_boto3(
            object_path=f"{s3_path_prefix}/user_a_file.txt",
            s3_storage_config=self.s3_storage_config,
            user=self.valid_user,
            expected_status=200,
        )

    def test_create_task_format_error(self):
        """
        Test Case: Verify that creating a TES task with an invalid request format returns a 400 error.
        - Attempt to create a TES task with missing required fields and invalid command format
        - Verify that the response status is 400 Bad Request
        """
        # Note: These tests are a part of integration tests instead of unit tests,
        # since the error is thrown by funnel and not gen3-workflow,
        # and we want to verify that the error is properly propagated through gen3-workflow's API.

        # Missing required 'executors' field
        invalid_payload_1 = {
            "name": "Invalid Task 1",
            "description": "This task is missing the 'executors' field.",
            "tags": {"user": self.valid_user},
        }
        self.gen3_workflow.create_tes_task(
            request_body=invalid_payload_1,
            user=self.valid_user,
            expected_status=400,
        )

        # Invalid command format (should be a list of strings)
        invalid_payload_2 = {
            "name": "Invalid Task 2",
            "description": "This task has an invalid command format.",
            "executors": [
                {
                    "image": "public.ecr.aws/docker/library/alpine:latest",
                    "command": "not_a_list",  # Invalid command format
                }
            ],
            "tags": {"user": self.valid_user},
        }
        self.gen3_workflow.create_tes_task(
            request_body=invalid_payload_2,
            user=self.valid_user,
            expected_status=400,
        )

    # TODO:
    # * Test the GET /ga4gh/tes/v1/tasks/<task_id> endpoint with a task id that is not present in the system, and expect a 404 from gen3-workflow
    # * Test the POST /ga4gh/tes/v1/tasks:cancel with a task id that is not present in the system, and expect a 404 from gen3-workflow
    # * Test the POST /ga4gh/tes/v1/tasks/<task_id>:cancel endpoint with a task that has already reached a final state,
    #   and expect a 200 from gen3-workflow with an error message in the response body indicating that the task cannot be cancelled
    # * Test the POST /ga4gh/tes/v1/tasks/ to `verify incremental-upload`. #48 "Operation not permitted" on output files should return a 200
    # * Test the s3 endpoint by uploading a large file(say 20MB) to test multipart upload logic by Gen3-workflow.
    # * Test the multi-user setup, where User A has access to User B's tasks, but not their storage.
