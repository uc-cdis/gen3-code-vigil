# pylint: disable=missing-function-docstring

"""
TODO update this

Usage:
- Install the Gen3 SDK
- Save your API key at`~/.gen3/credentials.json`
- Get your bucket and bucket region: `gen3 run sh -c 'curl -X GET <endpoint>/workflows/storage/setup --header "authorization: bearer $GEN3_TOKEN" | jq'`
- Configure `ENDPOINT`, `BUCKET` and `BUCKET_REGION` below
- Switch to this directory
- Launch with `gen3 run python performance_test.py`
"""

import asyncio
import json
import os
import random
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from statistics import mean, stdev
from typing import Dict, List

import boto3
import pytest
import requests
from botocore.config import Config
from gen3.auth import (
    Gen3Auth,
    endpoint_from_token,
    remove_trailing_whitespace_and_slashes_in_url,
)

# from cdislogging import get_logger
from utils import LOAD_TESTING_OUTPUT_PATH, load_test, logger

# ENDPOINT = "https://brhstaging.data-commons.org"
# BUCKET = "gen3wf-brhstaging-data-commons-org-35"
# BUCKET_REGION = "us-east-1"
BUCKET = "TODO"

VERBOSE = False  # if false, details are not on stdout but are still in the log file
INCLUDE_TIMESTAMPS_IN_LOGS = False
N_SEQ_RUNS = 3  # stats will be the average of the sequential runs stats
RUN_TIMEOUT = 1200  # 10 min

TESTS = [
    # {
    #     "name": "Random failures",
    #     "type": "Random",
    #     "n_sequential_runs": N_SEQ_RUNS,
    #     "n_concurrent_runs": 5,
    # },
]

# Nextflow tests
# for concurrency in [5, 10]:
#     for n_tasks in [1, 5]:
#         # Note: Nextflow tests always include inputs/outputs
#         TESTS.append(
#             {
#                 "name": f"Nextflow test ({n_tasks} tasks, concurrency {concurrency})",
#                 "type": "Nextflow",
#                 "n_sequential_runs": N_SEQ_RUNS,
#                 "n_concurrent_runs": concurrency,
#                 "n_tasks": n_tasks,
#                 "gpu": False,
#                 "workflow_file": "hello.nf",
#             }
#         )
#         TESTS.append(
#             {
#                 "name": f"Nextflow GPU test ({n_tasks} tasks, concurrency {concurrency})",
#                 "type": "Nextflow",
#                 "n_sequential_runs": N_SEQ_RUNS,
#                 "n_tasks": n_tasks,
#                 "n_concurrent_runs": concurrency,
#                 "gpu": True,
#                 "workflow_file": "gpu.nf",
#             }
#         )

# # TES tests
# for concurrency in [50, 100, 150, 200]:
#     TESTS.append(
#         {
#             "name": f"TES test (concurrency {concurrency})",
#             "type": "TES",
#             "n_sequential_runs": N_SEQ_RUNS,
#             "n_concurrent_runs": concurrency,
#             "body": {
#                 "name": f"Hello-World (concurrency {concurrency})",
#                 "executors": [
#                     {
#                         "image": "quay.io/nextflow/bash",
#                         "command": [
#                             "sleep SLEEP_TIME_PLACEHOLDER && echo hello world!"
#                         ],
#                     }
#                 ],
#             },
#         }
#     )
#     TESTS.append(
#         {
#             "name": f"TES GPU test (concurrency {concurrency})",
#             "type": "TES",
#             "n_sequential_runs": N_SEQ_RUNS,
#             "n_concurrent_runs": concurrency,
#             "body": {
#                 "name": f"Hello-World (GPU, concurrency {concurrency})",
#                 "tags": {"_GPU": "yes"},
#                 "executors": [
#                     {
#                         "image": "quay.io/nextflow/bash",
#                         "command": [
#                             "sleep SLEEP_TIME_PLACEHOLDER && echo hello world!"
#                         ],
#                     }
#                 ],
#             },
#         }
#     )
#     TESTS.append(
#         {
#             "name": f"TES test with inputs/outputs (concurrency {concurrency})",
#             "type": "TES",
#             "n_sequential_runs": N_SEQ_RUNS,
#             "n_concurrent_runs": concurrency,
#             "body": {
#                 "name": "Input-Output-Test",
#                 "inputs": [
#                     {
#                         "url": f"s3://{BUCKET}/inputs/test-file.txt",
#                         "path": "/work/test-file.txt",
#                         "type": "FILE",
#                     }
#                 ],
#                 "outputs": [
#                     {
#                         "url": f"s3://{BUCKET}/outputs/output.txt",
#                         "path": "/work/output.txt",
#                         "type": "FILE",
#                     }
#                 ],
#                 "executors": [
#                     {
#                         "image": "quay.io/nextflow/bash",
#                         "workdir": "/work",
#                         "command": [
#                             "sleep SLEEP_TIME_PLACEHOLDER && cat test-file.txt && echo hello > output.txt"
#                         ],
#                     }
#                 ],
#             },
#         }
#     )


SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "../test_data/tes_performance_scripts"
)
# logger = get_logger("tes-perf", log_level="debug" if VERBOSE else "info")
# log_file = None


# TODO move to utils file
def percentile(values, p):
    if not values:
        return 0

    values = sorted(values)
    index = int(len(values) * (p / 100))

    # prevent out-of-range index
    index = min(index, len(values) - 1)

    return values[index]


@dataclass
class RunStats:
    test_name: str
    seq_id: int
    conc_id: int
    successful: float
    run_time: float
    return_code: int


@pytest.fixture
def get_log_file():
    LOG_FILE_NAME = f"output/{int(time.time())}_logs.txt"  # TODO add test params
    print(f"Printing to {LOG_FILE_NAME}")
    log_file = open(LOG_FILE_NAME, "w")
    yield log_file
    log_file.close()


def log(log_file, level, msg):
    # print to terminal
    if INCLUDE_TIMESTAMPS_IN_LOGS:
        getattr(logger, level)(msg)
    else:
        if level != "debug" or VERBOSE:
            print(msg)

    # print to file
    if type(msg) == bytes:
        msg = msg.decode()
    log_file.write(msg + "\n")


def seconds_to_human_format(total_seconds):
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    res = ""
    if hours:
        res += f"{int(hours)}h "
    if minutes:
        res += f"{int(minutes)}m "
    res += f"{int(seconds)}s"
    return res


def print_stats(log_file, stats_list, total_run_time=None):
    n_runs = len(stats_list)
    n_successful_runs = 0
    avg_run_time = 0
    total_time_failed = 0
    all_run_times = []
    successful_run_times = []

    for m in stats_list:
        avg_run_time += m.run_time
        all_run_times.append(m.run_time)
        if not m.successful:
            total_time_failed += m.run_time
            continue
        n_successful_runs += 1
        successful_run_times.append(m.run_time)

    avg_run_time = avg_run_time / n_runs
    n_failed_runs = n_runs - n_successful_runs

    log(log_file, "info", f"Number of runs: {n_runs}")
    if total_run_time:
        log(
            log_file,
            "info",
            f"Total run time: {seconds_to_human_format(total_run_time)}",
        )
    log(log_file, "info", f"Successful runs: {n_successful_runs}")
    if n_runs:
        log(log_file, "info", f"Success rate: {n_successful_runs / n_runs * 100:.2f}%")
    log(
        log_file,
        "info",
        f"Average run time (all runs): {seconds_to_human_format(avg_run_time)}",
    )
    if n_successful_runs:
        log(
            log_file,
            "info",
            f"Average run time (successful runs): {seconds_to_human_format(sum(successful_run_times) / n_successful_runs)}",
        )
        log(
            log_file,
            "info",
            f"Min run time (successful runs): {seconds_to_human_format(min(successful_run_times))}",
        )
        log(
            log_file,
            "info",
            f"Max run time (successful runs): {seconds_to_human_format(max(successful_run_times))}",
        )
    if n_failed_runs:
        log(
            log_file,
            "info",
            f"Average run time (failed runs): {seconds_to_human_format(total_time_failed / n_failed_runs)}",
        )
    if len(successful_run_times) > 1:
        log(
            log_file,
            "info",
            f"Run time standard deviation (successful runs): {seconds_to_human_format(stdev(successful_run_times))}",
        )
    log(log_file, "info", "")

    summary = {
        "metrics": {
            "checks": {
                "passes": n_successful_runs,
                "fails": n_failed_runs,
                "value": (
                    round(n_successful_runs / (n_successful_runs + n_failed_runs), 4)
                    if (n_successful_runs + n_failed_runs)
                    else 0
                ),
                # "rate": (
                #     round((passes / iterations) * 100, 2) if (passes + fails) else 0
                # ),
            },
            "iterations": {
                # "count": iterations,
                # "rate": round(iterations / test_duration_seconds, 2),
            },
            "http_req_duration": {
                "min": round(min(all_run_times), 2),
                "avg": round(mean(all_run_times), 2),
                "med": round(percentile(all_run_times, 50), 2),
                "max": round(max(all_run_times), 2),
                "p(90)": round(percentile(all_run_times, 90), 2),
                "p(95)": round(percentile(all_run_times, 95), 2),
            },
            "data_sent": {"count": 0, "rate": 0},
        }
    }
    return summary


async def run_command(
    log_file, cmd: List[str], seq_id: int, conc_id: int, config: dict, env: dict = {}
) -> RunStats:
    test_name = config["name"]

    try:
        loop = asyncio.get_event_loop()
        start_time = time.time()
        # Each process runs in its own temp directory to avoid conflicts.
        # For example, if multiple Nextflow processes run at the same time in the same dir:
        # `Can't lock file: .nextflow/history -- Nextflow needs to run in a file system that
        # supports file locks`
        with tempfile.TemporaryDirectory() as temp_dir:
            result = await loop.run_in_executor(
                None,  # uses default ThreadPoolExecutor
                lambda: subprocess.run(
                    cmd,
                    env={**os.environ.copy(), **env},
                    capture_output=True,
                    text=True,
                    timeout=RUN_TIMEOUT,
                    cwd=temp_dir,
                ),
            )
        run_time = time.time() - start_time

        successful = True
        if result.returncode != 0 or "ERROR" in result.stdout:
            successful = False
        log(
            log_file,
            "debug",
            f"    '{test_name}' run 'seq{seq_id}-conc{conc_id}' {'completed' if successful else 'failed'} in {run_time:.2f}s",
        )
        if not successful:
            stdout = f"{result.stdout}\n---\n" if result.stdout else ""
            log(
                log_file,
                "debug",
                f"    Error code: {result.returncode}. Logs:\n{stdout}{result.stderr}",
            )
        elif result.stdout:
            log(log_file, "debug", f"    Logs:\n{result.stdout}")

        return RunStats(
            test_name=test_name,
            seq_id=seq_id,
            conc_id=conc_id,
            successful=successful,
            run_time=run_time,
            return_code=result.returncode,
        )

    except Exception as e:
        log(
            log_file,
            "error",
            f"❌ '{test_name}' run 'seq{seq_id}-conc{conc_id}' failed: {e}",
        )
        run_time = 0
        if type(e) == subprocess.TimeoutExpired:
            run_time = RUN_TIMEOUT
            log(log_file, "debug", "Timed out. Logs:\n")
            if e.stdout:
                for line in e.stdout.split(b"\n"):
                    log(log_file, "debug", line)
            if e.stderr:
                for line in e.stderr.split(b"\n"):
                    log(log_file, "debug", line)
        return RunStats(
            test_name=test_name,
            seq_id=seq_id,
            conc_id=conc_id,
            successful=False,
            run_time=run_time,
            return_code=-1,
        )


async def run_random_failures(
    log_file, seq_id: int, conc_id: int, config: dict, endpoint: str, bucket: str
) -> RunStats:
    r = random.randint(-2, 3)
    # print(f"Random failure: {r=}")
    cmd = ["sleep", str(r)]
    return await run_command(log_file, cmd, seq_id, conc_id, config)


class TestTesPerformance:
    @classmethod
    def setup_class(cls):
        cls.BASE_URL = f"{pytest.root_url}"

    #     cls.auth = Gen3Auth(
    #         refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
    #     )

    # TODO any way to import code from gen3-int-tests instead of duplicating?
    # TODO if not, move these functions to services/gen3-workflow
    from unittest.mock import patch

    @patch("gen3.auth.endpoint_from_token")
    def _get_access_token(
        self, user: str = "main_account", endpoint_from_token_mock=None
    ) -> str:
        """Helper function to retrieve an access token."""

        if not user:
            return None

        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)

        # When running the tests in a Kind cluster:
        # - Fence's `BASE_URL` is set to `http://fence-service.<namespace>.svc.cluster.local`, so
        #   API keys and access tokens have that as their issuer. This allows other pods in the
        #   cluster to reach Fence to validate tokens.
        # - However, the tests cannot reach this URL from outside the cluster. The cluster is
        #   exposed at `http://localhost:8000` and that's where the tests can reach Fence to obtain
        #   access tokens.
        # - The SDK's `endpoint_from_token` method extracts the endpoint from the API key. We mock
        #   this method to return `http://localhost:8000` instead of `http://fence-service.
        #   <namespace>.svc.cluster.local` so `Gen3Auth` knows to reach Fence there.
        # - Note: Setting Fence's `BASE_URL` to `http://localhost:8000` would fix this on the tests
        #   side, but other pods in the cluster would not be able to reach Fence to validate tokens
        #   (because within a container, localhost refers to the container itself).
        if "localhost" in self.BASE_URL:
            endpoint_from_token_mock.return_value = (
                remove_trailing_whitespace_and_slashes_in_url(self.BASE_URL)
            )
        else:  # otherwise, no mocking
            endpoint_from_token_mock.side_effect = lambda arg: endpoint_from_token(arg)
        endpoint_from_token_mock.return_value = (
            remove_trailing_whitespace_and_slashes_in_url(self.BASE_URL)
        )

        try:
            return auth.get_access_token()
        except Exception:
            logger.info("Failed to get access token with Gen3Auth")
            raise

    def setup_storage(self, user: str = "main_account", expected_status=200) -> Dict:
        """Makes a GET request to the `/storage/setup` endpoint."""
        storage_url = f"{self.BASE_URL}/workflows/storage/setup"
        headers = (
            {
                "Authorization": f"bearer {self._get_access_token(user)}",
            }
            if user
            else {}
        )

        response = requests.get(url=storage_url, headers=headers)
        # if response.status_code != expected_status:
        #     _print_tes_apps_logs(with_arborist=response.status_code == 403)
        assert (
            response.status_code == expected_status
        ), f"Expected {expected_status}, got {response.status_code} when making a GET request to {storage_url}: {response.text}"
        storage_info = response.json()
        assert isinstance(storage_info, dict), "Expected a valid JSON response"
        return storage_info

    async def run_nextflow_workflow(
        self,
        log_file,
        seq_id: int,
        conc_id: int,
        config: dict,
        endpoint: str,
        bucket: str,
    ) -> RunStats:
        cmd = [
            # "gen3",
            # "run",
            "nextflow",
            "run",
            os.path.join(SCRIPTS_DIR, config["workflow_file"]),
            "-c",
            os.path.join(SCRIPTS_DIR, "base_nextflow.config"),
            "--n_tasks",
            f"{config['n_tasks']}",
        ]
        return await run_command(
            log_file,
            cmd,
            seq_id,
            conc_id,
            config,
            {
                "GEN3_TOKEN": self._get_access_token("main_account"),
                "ENDPOINT": endpoint,
                "BUCKET": bucket,
                "GPU": "yes" if config["gpu"] else "no",
            },
        )

    async def run_tes_task(
        self,
        log_file,
        seq_id: int,
        conc_id: int,
        config: dict,
        endpoint: str,
        bucket: str,
    ) -> RunStats:
        sleep_time = random.randint(0, 5)
        body = config["body"]
        body["executors"][0]["command"][0] = body["executors"][0]["command"][0].replace(
            "SLEEP_TIME_PLACEHOLDER", str(sleep_time)
        )
        cmd = [
            # "gen3",
            # "run",
            # f"GEN3_TOKEN={self._get_access_token("main_account")}"
            "python",
            os.path.join(SCRIPTS_DIR, "run_tes_task.py"),
            endpoint,
            json.dumps(body),
        ]
        return await run_command(
            log_file,
            cmd,
            seq_id,
            conc_id,
            config,
            {"GEN3_TOKEN": self._get_access_token("main_account")},
        )

    @pytest.mark.asyncio
    async def test_tes_performance(self, get_log_file):
        # try:
        #     asyncio.run(run_tests(LOG_FILE_NAME))
        # except KeyboardInterrupt:
        #     log(log_file, "exception", "Test interrupted by user")
        #     sys.exit(1)
        # except Exception as e:
        #     log(log_file, "exception", f"❌ Test failed with error: {e}")
        #     raise
        # finally:

        log_file = get_log_file
        concurrency = 2

        # NOTE def run_tests(log_file_name) was here

        s3_storage_config = self.setup_storage()
        # (
        #     =data["bucket"],
        #     =data["workdir"],
        #     =data["region"],
        # )

        # upload the input file used by TES tests
        s3_client = boto3.client(
            service_name="s3",
            aws_access_key_id=self._get_access_token(
                "main_account"
            ),  # self.auth.get_access_token(), #os.environ["GEN3_TOKEN"],
            aws_secret_access_key="N/A",
            endpoint_url=f"{self.BASE_URL}/workflows/s3",
            config=Config(region_name=s3_storage_config["region"]),
        )
        s3_client.put_object(
            Bucket=s3_storage_config["bucket"],
            Key="inputs/test-file.txt",
            Body="this is my test file\n",
        )

        test_start = time.perf_counter()
        # total_start_time = time.time()
        # for test_i, config in enumerate(TESTS, start=1):
        test_i = 1
        if True:
            # config = {
            #     "name": "Random failures",
            #     "type": "Random",
            #     "n_sequential_runs": N_SEQ_RUNS,
            #     "n_concurrent_runs": 5,
            # }
            config = {
                "name": f"TES test (concurrency {concurrency})",
                "type": "TES",
                "n_sequential_runs": N_SEQ_RUNS,
                "n_concurrent_runs": concurrency,
                "body": {
                    "name": f"Hello-World (concurrency {concurrency})",
                    "executors": [
                        {
                            "image": "quay.io/nextflow/bash",
                            "command": [
                                "sleep SLEEP_TIME_PLACEHOLDER && echo hello world!"
                            ],
                        }
                    ],
                },
            }

            log(
                log_file,
                "info",
                f"[test {test_i}/{len(TESTS)}] '{config['name']}' starting",
            )

            # launch `n_sequential_runs` sequential runs
            all_stats = []
            # for seq_run in range(1, config["n_sequential_runs"] + 1):
            seq_run = 1
            if True:
                _type = config["type"]
                if _type == "Random":
                    method = run_random_failures
                elif _type == "Nextflow":
                    method = self.run_nextflow_workflow
                elif _type == "TES":
                    method = self.run_tes_task
                else:
                    raise Exception(f"Unknown test type '{_type}'")

                # launch `n_concurrent_runs` concurrent runs
                n_concurrent_runs = config["n_concurrent_runs"]
                tasks = [
                    method(
                        log_file,
                        seq_id=seq_run,
                        conc_id=conc_run,
                        config=config,
                        endpoint=self.BASE_URL,
                        bucket=s3_storage_config["bucket"],
                    )
                    for conc_run in range(1, n_concurrent_runs + 1)
                ]
                # start_time = time.time()
                run_stats = await asyncio.gather(*tasks)
                # log(log_file,
                #     "info",
                #     f"[test {test_i}/{len(TESTS)}] [run {seq_run}/{config['n_sequential_runs']}] '{config['name']}' run stats:",
                # )
                # print_stats(run_stats, time.time() - start_time)
                all_stats.extend(run_stats)

        test_duration_seconds = time.perf_counter() - test_start
        log(
            log_file,
            "info",
            f"✅ [test {test_i}/{len(TESTS)}] '[{config['name']}]' final stats:",
        )
        summary = print_stats(log_file, all_stats, test_duration_seconds)
        # log(log_file,
        #     "info",
        #     f"Total run time: {seconds_to_human_format(time.time() - total_start_time)}. Find logs at '{log_file_name}'.",
        # )
        # print(summary)

        service = "gen3-workflow"
        scenario = f"test_tes_performance[{concurrency}]"
        file_name = f"{service}-{scenario}.json"
        output_path = LOAD_TESTING_OUTPUT_PATH / file_name
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)

        load_test.get_results(
            # result,
            None,
            service=service,
            load_test_scenario=scenario,
            # append_file_name=f"gen3sdk[{collection_name}-{number_of_records}-{dimensions}]",
        )
