# pylint: disable=missing-function-docstring

"""
Can be configured with PARAMS (as a JSON string); example:
{
    "tes": {
        "concurrency": [500, 1000],
        "test_case_simple": true,
        "test_case_inputs_outputs": true,
        "test_case_gpu": true
    },
    "nextflow": {
        "concurrency": [5, 10],
        "n_tasks": [1, 5],
        "test_case_simple": true,
        "test_case_gpu": true
    }
}
Configuring the TES or Nextflow `concurrency` to `[]` skips those tests.
"""

import asyncio
import json
import os
import random
import subprocess
import tempfile
import time
from dataclasses import dataclass
from statistics import mean, stdev
from typing import List

import boto3
import pytest
from botocore.config import Config
from services.gen3workflow import _get_access_token, cleanup_user_bucket, setup_storage
from utils import LOAD_TESTING_OUTPUT_PATH, load_test, logger
from utils.misc import percentile
from utils.test_execution import attach_output_file

VERBOSE = True  # if false, details are not on stdout but are still in the log file
INCLUDE_TIMESTAMPS_IN_LOGS = False
RUN_TIMEOUT = 1200  # 10 min
LOG_FILE_NAME = f"gen3-workflow-tes-performance-logs-{int(time.time())}.txt"

LOG_FILE_PATH = LOAD_TESTING_OUTPUT_PATH / LOG_FILE_NAME
SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "../test_data/tes_performance_scripts"
)
PARAMS = json.loads(os.getenv("PARAMS", {}))

TESTS = [
    # {
    #     "name": "Random failures",
    #     "type": "Random",
    #     "n_concurrent_runs": 5,
    # },
]

# Nextflow tests
for concurrency in PARAMS.get("nextflow", {}).get("concurrency", [5, 10, 20]):
    for n_tasks in PARAMS.get("nextflow", {}).get("n_tasks", [1, 5]):
        if PARAMS.get("nextflow", {}).get("test_case_simple", True):
            # Note: Nextflow tests always include inputs/outputs
            TESTS.append(
                {
                    "name": f"Nextflow test ({n_tasks} tasks, concurrency {concurrency})",
                    "type": "Nextflow",
                    "n_concurrent_runs": concurrency,
                    "n_tasks": n_tasks,
                    "gpu": False,
                    "workflow_file": "hello.nf",
                }
            )
        if PARAMS.get("nextflow", {}).get("test_case_gpu", True):
            TESTS.append(
                {
                    "name": f"Nextflow GPU test ({n_tasks} tasks, concurrency {concurrency})",
                    "type": "Nextflow",
                    "n_tasks": n_tasks,
                    "n_concurrent_runs": concurrency,
                    "gpu": True,
                    "workflow_file": "gpu.nf",
                }
            )

# TES tests
for concurrency in PARAMS.get("tes", {}).get("concurrency", [5, 100]):
    if PARAMS.get("tes", {}).get("test_case_simple", True):
        TESTS.append(
            {
                "name": f"TES test (concurrency {concurrency})",
                "type": "TES",
                "n_concurrent_runs": concurrency,
                "payload": {
                    "name": f"Hello-World (concurrency {concurrency})",
                    "executors": [
                        {
                            "image": "public.ecr.aws/docker/library/alpine:latest",
                            "command": [
                                "sleep SLEEP_TIME_PLACEHOLDER && echo hello world!"
                            ],
                        }
                    ],
                },
            }
        )
    if PARAMS.get("tes", {}).get("test_case_inputs_outputs", True):
        TESTS.append(
            {
                "name": f"TES test with inputs-outputs (concurrency {concurrency})",
                "type": "TES",
                "n_concurrent_runs": concurrency,
                "payload": {
                    "name": "Input-Output-Test",
                    "inputs": [
                        {
                            "url": f"s3://BUCKET_PLACEHOLDER/inputs/test-file.txt",
                            "path": "/work/test-file.txt",
                            "type": "FILE",
                        }
                    ],
                    "outputs": [
                        {
                            "url": f"s3://BUCKET_PLACEHOLDER/outputs/output.txt",
                            "path": "/work/output.txt",
                            "type": "FILE",
                        }
                    ],
                    "executors": [
                        {
                            "image": "public.ecr.aws/docker/library/alpine:latest",
                            "workdir": "/work",
                            "command": [
                                "sleep SLEEP_TIME_PLACEHOLDER && cat test-file.txt && echo hello > output.txt"
                            ],
                        }
                    ],
                },
            }
        )
    if PARAMS.get("tes", {}).get("test_case_gpu", True):
        # Note: the command doesn't actually need a GPU, we only test scheduling on the GPU node
        TESTS.append(
            {
                "name": f"TES GPU test (concurrency {concurrency})",
                "type": "TES",
                "n_concurrent_runs": concurrency,
                "payload": {
                    "name": f"Hello-World (GPU, concurrency {concurrency})",
                    "tags": {"_GPU": "yes"},
                    "executors": [
                        {
                            "image": "public.ecr.aws/docker/library/alpine:latest",
                            "command": [
                                "sleep SLEEP_TIME_PLACEHOLDER && echo hello world!"
                            ],
                        }
                    ],
                },
            }
        )

logger.info(f"Running test cases: {[t['name'] for t in TESTS]}")


@dataclass
class RunStats:
    test_name: str
    conc_id: int
    successful: float
    run_time: float
    return_code: int


@pytest.fixture(scope="session")
def log_file():
    logger.info(f"Printing to {LOG_FILE_PATH}")
    log_file = open(LOG_FILE_PATH, "a")
    yield log_file
    log_file.close()


def log(log_file, level, msg):
    # print to terminal
    if INCLUDE_TIMESTAMPS_IN_LOGS:
        getattr(logger, level)(msg)
    else:
        if level != "debug" or VERBOSE:
            print(msg)

    # print to log file
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


def print_stats(log_file, stats_list, run_time_seconds):
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
    log(
        log_file,
        "info",
        f"Total run time: {seconds_to_human_format(run_time_seconds)}",
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
            },
            "iterations": {
                "count": n_runs,
                "rate": round(n_runs / run_time_seconds, 2),
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
    log_file, cmd: List[str], conc_id: int, config: dict, env: dict = {}
) -> RunStats:
    test_name = config["name"]

    try:
        loop = asyncio.get_event_loop()
        start_time = time.perf_counter()
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
        run_time = time.perf_counter() - start_time

        successful = True
        if result.returncode != 0 or "ERROR" in result.stdout:
            successful = False
        log(
            log_file,
            "debug",
            f"    '{test_name}' run {conc_id} {'completed' if successful else 'failed'} in {run_time:.2f}s",
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
            conc_id=conc_id,
            successful=successful,
            run_time=run_time,
            return_code=result.returncode,
        )

    except Exception as e:
        log(
            log_file,
            "error",
            f"❌ '{test_name}' run {conc_id} failed: {e}",
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
            conc_id=conc_id,
            successful=False,
            run_time=run_time,
            return_code=-1,
        )


async def run_random_failures(
    log_file, conc_id: int, config: dict, **kwargs
) -> RunStats:
    r = random.randint(-2, 3)
    # log(f"Random failure: {r=}")
    cmd = ["sleep", str(r)]
    return await run_command(log_file, cmd, conc_id, config)


async def run_tes_task(
    log_file,
    conc_id: int,
    config: dict,
    endpoint: str,
    bucket: str,
) -> RunStats:
    # simulate tasks that take 0 to 5s to complete
    sleep_time = random.randint(0, 5)
    payload = config["payload"]
    payload["executors"][0]["command"][0] = payload["executors"][0]["command"][
        0
    ].replace("SLEEP_TIME_PLACEHOLDER", str(sleep_time))
    for field in ["inputs", "outputs"]:
        try:
            payload[field][0]["url"] = payload[field][0]["url"].replace(
                "BUCKET_PLACEHOLDER", bucket
            )
        except Exception:
            pass

    cmd = [
        "python",
        os.path.join(SCRIPTS_DIR, "run_tes_task.py"),
        endpoint,
        json.dumps(payload),
    ]
    return await run_command(
        log_file,
        cmd,
        conc_id,
        config,
        {"GEN3_TOKEN": _get_access_token("main_account")},
    )


async def run_nextflow_workflow(
    log_file,
    conc_id: int,
    config: dict,
    endpoint: str,
    bucket: str,
) -> RunStats:
    cmd = [
        "python",
        os.path.join(SCRIPTS_DIR, "run_nextflow_workflow.py"),
        os.path.join(SCRIPTS_DIR, config["workflow_file"]),
        os.path.join(SCRIPTS_DIR, "base_nextflow.config"),
        str(config["n_tasks"]),
    ]
    return await run_command(
        log_file,
        cmd,
        conc_id,
        config,
        {
            "GEN3_TOKEN": _get_access_token("main_account"),
            "ENDPOINT": endpoint,
            "BUCKET": bucket,
            "GPU": "yes" if config["gpu"] else "no",
        },
    )


class TestTesPerformance:
    @classmethod
    def setup_class(cls):
        cls.s3_storage_config = setup_storage()
        cleanup_user_bucket()

        # upload the input file used by TES tests
        s3_client = boto3.client(
            service_name="s3",
            aws_access_key_id=_get_access_token("main_account"),
            aws_secret_access_key="N/A",
            endpoint_url=f"{pytest.root_url}/workflows/s3",
            config=Config(region_name=cls.s3_storage_config["region"]),
        )
        s3_client.put_object(
            Bucket=cls.s3_storage_config["bucket"],
            Key="inputs/test-file.txt",
            Body="this is my test file\n",
        )

    @pytest.fixture(scope="class", autouse=True)
    def print_logs_at_end_of_tests(self):
        yield
        with open(LOG_FILE_PATH, "r") as f:
            print(f"{LOG_FILE_PATH}:\n{f.read()}")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "config", [pytest.param(config, id=config["name"]) for config in TESTS]
    )
    async def test_gen3_workflow_tes_performance(self, log_file, config):

        test_start = time.perf_counter()
        log(log_file, "info", f"'{config['name']}' starting")

        _type = config["type"]
        if _type == "Random":
            method = run_random_failures
        elif _type == "Nextflow":
            method = run_nextflow_workflow
        elif _type == "TES":
            method = run_tes_task
        else:
            raise Exception(f"Unknown test type '{_type}'")

        # launch `n_concurrent_runs` concurrent runs
        n_concurrent_runs = config["n_concurrent_runs"]
        tasks = [
            method(
                log_file,
                conc_id=conc_run,
                config=config,
                endpoint=pytest.root_url,
                bucket=self.s3_storage_config["bucket"],
            )
            for conc_run in range(1, n_concurrent_runs + 1)
        ]
        run_stats = await asyncio.gather(*tasks)

        test_duration_seconds = time.perf_counter() - test_start
        log(
            log_file,
            "info",
            f"✅ '{config['name']}' stats:",
        )
        summary = print_stats(log_file, run_stats, test_duration_seconds)

        service = "gen3-workflow"
        scenario = f"tes-performance[{config['name']}]"
        file_name = f"{service}-{scenario}.json"
        output_path = LOAD_TESTING_OUTPUT_PATH / file_name
        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)

        load_test.get_results(
            None,
            service=service,
            load_test_scenario=scenario,
        )
        attach_output_file(LOG_FILE_NAME)
