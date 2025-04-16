import json
import os
import subprocess

import pytest
from utils import K6_LOAD_TESTING_OUTPUT_PATH, K6_LOAD_TESTING_SCRIPTS_PATH, logger


def run_k6_load_test(env_vars, service, load_test_scenario):
    js_script_path = K6_LOAD_TESTING_SCRIPTS_PATH / f"{service}-{load_test_scenario}.js"
    output_path = K6_LOAD_TESTING_OUTPUT_PATH / f"{service}-{load_test_scenario}.json"
    result = subprocess.run(
        ["k6", "run", js_script_path, f"--summary-export={output_path}"],
        capture_output=True,
        text=True,
        env={**env_vars, **dict(os.environ)},
    )
    return result


def get_k6_results(k6_output, service, load_test_scenario):
    output_path = K6_LOAD_TESTING_OUTPUT_PATH / f"{service}-{load_test_scenario}.json"
    output = json.loads(output_path.read_text())
    passed = str(output["metrics"]["checks"]["passes"])
    failed = str(output["metrics"]["checks"]["fails"])
    pass_rate = round(float(output["metrics"]["checks"]["value"]) * 100, 2)
    logger.info(f"K6 Load Test Metrics for {service}-{load_test_scenario}:")
    logger.info(f"Passed   : {passed}")
    logger.info(f"Failed   : {failed}")
    logger.info(f"Pass Rate: {pass_rate}%")
    if pass_rate < pytest.pass_threshold:
        logger.info(k6_output.stdout)
        logger.info(k6_output.strerr)
        raise f"Pass rate is below threshold of {pytest.pass_threshold}%"
