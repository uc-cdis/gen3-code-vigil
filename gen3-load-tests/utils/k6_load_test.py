import os
import re
import subprocess

from utils import logger


def run_k6_load_test(env_vars, script_path):
    result = subprocess.run(
        ["k6", "run", script_path],
        capture_output=True,
        text=True,
        env={**env_vars, **dict(os.environ)},
    )
    return result


def get_k6_results(k6_output):
    total_checks = re.search(r"checks_total\.+: (\d+)", k6_output).group(1)
    passed_checks = re.search(
        r"checks_succeeded\.+: \d+\.?\d+% +(\d+) out of \d+", k6_output
    ).group(1)
    failed_checks = re.search(
        r"checks_failed\.+: \d+\.?\d+% +(\d+) out of \d+", k6_output
    ).group(1)
    passed_rate = re.search(
        r"checks_succeeded\.+: (\d+\.?\d+%) +\d+ out of \d+", k6_output
    ).group(1)
    failed_rate = re.search(
        r"checks_failed\.+: (\d+\.?\d+%) +\d+ out of \d+", k6_output
    ).group(1)

    logger.info(f"Total Checks: {total_checks}")
    logger.info(f"Passed Checks: {passed_checks}")
    logger.info(f"Failed Checks: {failed_checks}")
    logger.info(f"Pass Rate: {passed_rate}")
    logger.info(f"Fail Rate: {failed_rate}")
