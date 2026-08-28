# pylint: disable=missing-function-docstring

import json
import os
import shutil
import sys
import traceback
from pathlib import Path

import nextflow
import requests

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))


def main(workflow_script, nextflow_config_file, n_tasks):
    run_id = os.environ["RUN_ID"]
    print(f"Run ID: {run_id}")
    original_cwd = Path.cwd()
    workflow_files_dir = Path(CURRENT_DIR).resolve()
    workdir = workflow_files_dir / f".nextflow.{run_id}"
    workdir.mkdir(parents=True, exist_ok=True)

    try:
        os.chdir(workdir)
        try:
            execution = nextflow.run(
                workflow_script,
                configs=[nextflow_config_file],
                params={"n_tasks": n_tasks},
            )
        except Exception as e:
            traceback.print_exc()
            raise
        if execution.status != "OK":
            # get TES task details for debugging
            log_file_content = ""
            with open(".nextflow.log", "r") as log_file:
                log_file_content = log_file.read()
            try:
                parts = log_file_content.split("Created task with ID: ")
                for part in parts[1:]:
                    task_id = part.split(", name: ")[0]
                    response = requests.get(
                        f"{os.environ['ENDPOINT']}/workflows/ga4gh/tes/v1/tasks/{task_id}?view=FULL",
                        headers={"authorization": f"bearer {os.environ['GEN3_TOKEN']}"},
                        timeout=60,
                    )
                    assert response.status_code == 200, response.text
                    print(
                        f"Task '{task_id}' details: {json.dumps(response.json(), indent=2)}"
                    )
            except Exception as e:
                print(f"Unable to get task details: {e}")
            raise Exception(
                f"Nextflow workflow execution failed with status: {execution.status} and log:\n{log_file_content}"
            )
    finally:
        # Change back to the original workdir, move the log file and delete the temp workdir.
        # Note: we should be able to configure nextflow to use a different log file, but it makes
        # the `nextflow.py` lib call hang, so moving it manually instead.
        os.chdir(original_cwd)
        shutil.move(
            workdir / ".nextflow.log", workflow_files_dir / f".nextflow.log_{run_id}"
        )
        shutil.rmtree(workdir)


if __name__ == "__main__":
    try:
        assert len(sys.argv) == 4, "Incorrect number of arguments"
        main(sys.argv[1], sys.argv[2], sys.argv[3])
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
