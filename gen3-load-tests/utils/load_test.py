import json
import os
import subprocess

import pytest
from utils import LOAD_TESTING_OUTPUT_PATH, LOAD_TESTING_SCRIPTS_PATH, logger
from utils.test_execution import attach_json_file


def run_load_test(env_vars):
    service = env_vars["SERVICE"]
    load_test_scenario = env_vars["LOAD_TEST_SCENARIO"]
    js_script_path = LOAD_TESTING_SCRIPTS_PATH / f"{service}-{load_test_scenario}.js"
    output_path = LOAD_TESTING_OUTPUT_PATH / f"{service}-{load_test_scenario}.json"
    logger.info(f"Running load test for {service}-{load_test_scenario}")
    result = subprocess.run(
        ["k6", "run", js_script_path, f"--summary-export={output_path}"],
        capture_output=True,
        text=True,
        env={**env_vars, **dict(os.environ)},
    )
    logger.info(result.stdout)
    logger.info(result.stderr)
    return result


def get_results(result, service, load_test_scenario):
    logger.info(f"Validating logs for {service}-{load_test_scenario}")
    output_path = LOAD_TESTING_OUTPUT_PATH / f"{service}-{load_test_scenario}.json"
    output = json.loads(output_path.read_text())
    passed = str(output["metrics"]["checks"]["passes"])
    failed = str(output["metrics"]["checks"]["fails"])
    pass_rate = round(float(output["metrics"]["checks"]["value"]) * 100, 2)
    attach_json_file(f"{service}-{load_test_scenario}.json")
    logger.info(f"Load Test Metrics for {service}-{load_test_scenario}:")
    logger.info(f"Passed   : {passed}")
    logger.info(f"Failed   : {failed}")
    logger.info(f"Pass Rate: {pass_rate}%")
    if pass_rate < pytest.pass_threshold:
        logger.info(result.stdout)
        logger.info(result.stderr)
        raise f"Pass rate is below threshold of {pytest.pass_threshold}%"
