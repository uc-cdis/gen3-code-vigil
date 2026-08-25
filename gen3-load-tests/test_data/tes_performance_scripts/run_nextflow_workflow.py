# pylint: disable=missing-function-docstring

import os
import sys
from pathlib import Path

import nextflow

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))


def main(workflow_script, nextflow_config_file, n_tasks):
    original_cwd = Path.cwd()
    workflow_dir_path = Path(CURRENT_DIR).resolve()

    try:
        os.chdir(workflow_dir_path)
        execution = nextflow.run(
            workflow_script, configs=[nextflow_config_file], params={"n_tasks": n_tasks}
        )
        log_file_content = ""
        with open(".nextflow.log", "r") as log_file:
            log_file_content = log_file.read()
        assert (
            execution.status == "OK"
        ), f"Nextflow workflow execution failed with status: {execution.status} and log:\n{log_file_content}"
    finally:
        # Change back to the original working directory
        os.chdir(original_cwd)


if __name__ == "__main__":
    try:
        assert len(sys.argv) == 4, "Incorrect number of arguments"
        main(sys.argv[1], sys.argv[2], sys.argv[3])
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
