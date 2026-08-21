# pylint: disable=missing-function-docstring

"""
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
from statistics import stdev
from typing import List

import boto3
from botocore.config import Config
from cdislogging import get_logger

ENDPOINT = "https://brhstaging.data-commons.org"
BUCKET = "gen3wf-brhstaging-data-commons-org-35"
BUCKET_REGION = "us-east-1"

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
for concurrency in [5, 10]:
    for n_tasks in [1, 5]:
        # Note: Nextflow tests always include inputs/outputs
        TESTS.append(
            {
                "name": f"Nextflow test ({n_tasks} tasks, concurrency {concurrency})",
                "type": "Nextflow",
                "n_sequential_runs": N_SEQ_RUNS,
                "n_concurrent_runs": concurrency,
                "n_tasks": n_tasks,
                "gpu": False,
                "workflow_file": "hello.nf",
            }
        )
        TESTS.append(
            {
                "name": f"Nextflow GPU test ({n_tasks} tasks, concurrency {concurrency})",
                "type": "Nextflow",
                "n_sequential_runs": N_SEQ_RUNS,
                "n_tasks": n_tasks,
                "n_concurrent_runs": concurrency,
                "gpu": True,
                "workflow_file": "gpu.nf",
            }
        )

# TES tests
for concurrency in [50, 100, 150, 200]:
    TESTS.append(
        {
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
    )
    TESTS.append(
        {
            "name": f"TES GPU test (concurrency {concurrency})",
            "type": "TES",
            "n_sequential_runs": N_SEQ_RUNS,
            "n_concurrent_runs": concurrency,
            "body": {
                "name": f"Hello-World (GPU, concurrency {concurrency})",
                "tags": {"_GPU": "yes"},
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
    )
    TESTS.append(
        {
            "name": f"TES test with inputs/outputs (concurrency {concurrency})",
            "type": "TES",
            "n_sequential_runs": N_SEQ_RUNS,
            "n_concurrent_runs": concurrency,
            "body": {
                "name": "Input-Output-Test",
                "inputs": [
                    {
                        "url": f"s3://{BUCKET}/inputs/test-file.txt",
                        "path": "/work/test-file.txt",
                        "type": "FILE",
                    }
                ],
                "outputs": [
                    {
                        "url": f"s3://{BUCKET}/outputs/output.txt",
                        "path": "/work/output.txt",
                        "type": "FILE",
                    }
                ],
                "executors": [
                    {
                        "image": "quay.io/nextflow/bash",
                        "workdir": "/work",
                        "command": [
                            "sleep SLEEP_TIME_PLACEHOLDER && cat test-file.txt && echo hello > output.txt"
                        ],
                    }
                ],
            },
        }
    )


CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
logger = get_logger("tes-perf", log_level="debug" if VERBOSE else "info")
log_file = None


@dataclass
class RunStats:
    test_name: str
    seq_id: int
    conc_id: int
    successful: float
    run_time: float
    return_code: int


def log(level, msg):
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


def print_stats(stats_list, total_run_time=None):
    n_runs = len(stats_list)
    n_successful_runs = 0
    avg_run_time = 0
    total_time_failed = 0
    successful_run_times = []

    for m in stats_list:
        avg_run_time += m.run_time
        if not m.successful:
            total_time_failed += m.run_time
            continue
        n_successful_runs += 1
        successful_run_times.append(m.run_time)

    avg_run_time = avg_run_time / n_runs
    n_failed_runs = n_runs - n_successful_runs

    log("info", f"Number of runs: {n_runs}")
    if total_run_time:
        log("info", f"Total run time: {seconds_to_human_format(total_run_time)}")
    log("info", f"Successful runs: {n_successful_runs}")
    if n_runs:
        log("info", f"Success rate: {n_successful_runs / n_runs * 100:.2f}%")
    log("info", f"Average run time (all runs): {seconds_to_human_format(avg_run_time)}")
    if n_successful_runs:
        log(
            "info",
            f"Average run time (successful runs): {seconds_to_human_format(sum(successful_run_times) / n_successful_runs)}",
        )
        log(
            "info",
            f"Min run time (successful runs): {seconds_to_human_format(min(successful_run_times))}",
        )
        log(
            "info",
            f"Max run time (successful runs): {seconds_to_human_format(max(successful_run_times))}",
        )
    if n_failed_runs:
        log(
            "info",
            f"Average run time (failed runs): {seconds_to_human_format(total_time_failed / n_failed_runs)}",
        )
    if len(successful_run_times) > 1:
        log(
            "info",
            f"Run time standard deviation (successful runs): {seconds_to_human_format(stdev(successful_run_times))}",
        )
    log("info", "")


async def run_command(
    cmd: List[str], seq_id: int, conc_id: int, config: dict, env: dict = {}
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
            "debug",
            f"    '{test_name}' run 'seq{seq_id}-conc{conc_id}' {'completed' if successful else 'failed'} in {run_time:.2f}s",
        )
        if not successful:
            stdout = f"{result.stdout}\n---\n" if result.stdout else ""
            log(
                "debug",
                f"    Error code: {result.returncode}. Logs:\n{stdout}{result.stderr}",
            )
        elif result.stdout:
            log("debug", f"    Logs:\n{result.stdout}")

        return RunStats(
            test_name=test_name,
            seq_id=seq_id,
            conc_id=conc_id,
            successful=successful,
            run_time=run_time,
            return_code=result.returncode,
        )

    except Exception as e:
        log("error", f"❌ '{test_name}' run 'seq{seq_id}-conc{conc_id}' failed: {e}")
        run_time = 0
        if type(e) == subprocess.TimeoutExpired:
            run_time = RUN_TIMEOUT
            log("debug", "Timed out. Logs:\n")
            if e.stdout:
                for line in e.stdout.split(b"\n"):
                    log("debug", line)
            if e.stderr:
                for line in e.stderr.split(b"\n"):
                    log("debug", line)
        return RunStats(
            test_name=test_name,
            seq_id=seq_id,
            conc_id=conc_id,
            successful=False,
            run_time=run_time,
            return_code=-1,
        )


async def run_random_failures(seq_id: int, conc_id: int, config: dict) -> RunStats:
    r = random.randint(-2, 3)
    cmd = ["sleep", str(r)]
    return await run_command(cmd, seq_id, conc_id, config)


async def run_nextflow_workflow(seq_id: int, conc_id: int, config: dict) -> RunStats:
    cmd = [
        "gen3",
        "run",
        "nextflow",
        "run",
        os.path.join(CURRENT_DIR, config["workflow_file"]),
        "-c",
        os.path.join(CURRENT_DIR, "base_nextflow.config"),
        "--n_tasks",
        f"{config['n_tasks']}",
    ]
    return await run_command(
        cmd,
        seq_id,
        conc_id,
        config,
        {
            "ENDPOINT": ENDPOINT,
            "BUCKET": BUCKET,
            "GPU": "yes" if config["gpu"] else "no",
        },
    )


async def run_tes_task(seq_id: int, conc_id: int, config: dict) -> RunStats:
    sleep_time = random.randint(0, 5)
    body = config["body"]
    body["executors"][0]["command"][0] = body["executors"][0]["command"][0].replace(
        "SLEEP_TIME_PLACEHOLDER", str(sleep_time)
    )
    cmd = [
        "gen3",
        "run",
        "python",
        os.path.join(CURRENT_DIR, "run_tes_task.py"),
        ENDPOINT,
        json.dumps(body),
    ]
    return await run_command(cmd, seq_id, conc_id, config)


async def run_tests(log_file_name):
    # upload the input file used by TES tests
    s3_client = boto3.client(
        service_name="s3",
        aws_access_key_id=os.environ["GEN3_TOKEN"],
        aws_secret_access_key="N/A",
        endpoint_url=f"{ENDPOINT}/workflows/s3",
        config=Config(region_name=BUCKET_REGION),
    )
    s3_client.put_object(
        Bucket=BUCKET, Key="inputs/test-file.txt", Body="this is my test file\n"
    )

    # run all the tests
    total_start_time = time.time()
    for test_i, config in enumerate(TESTS, start=1):
        log("info", f"[test {test_i}/{len(TESTS)}] '{config['name']}' starting")

        # launch `n_sequential_runs` sequential runs
        all_stats = []
        for seq_run in range(1, config["n_sequential_runs"] + 1):
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
                method(seq_id=seq_run, conc_id=conc_run, config=config)
                for conc_run in range(1, n_concurrent_runs + 1)
            ]
            start_time = time.time()
            run_stats = await asyncio.gather(*tasks)
            log(
                "info",
                f"[test {test_i}/{len(TESTS)}] [run {seq_run}/{config['n_sequential_runs']}] '{config['name']}' run stats:",
            )
            print_stats(run_stats, time.time() - start_time)
            all_stats.extend(run_stats)

        log(
            "info", f"✅ [test {test_i}/{len(TESTS)}] '[{config['name']}]' final stats:"
        )
        print_stats(all_stats)
    log(
        "info",
        f"Total run time: {seconds_to_human_format(time.time() - total_start_time)}. Find logs at '{log_file_name}'.",
    )


if __name__ == "__main__":
    LOG_FILE_NAME = f"{int(time.time())}_logs.txt"
    print(f"Printing to {LOG_FILE_NAME}")
    log_file = open(LOG_FILE_NAME, "w")
    try:
        asyncio.run(run_tests(LOG_FILE_NAME))
    except KeyboardInterrupt:
        log("exception", "Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        log("exception", f"❌ Test failed with error: {e}")
        raise
    finally:
        log_file.close()
