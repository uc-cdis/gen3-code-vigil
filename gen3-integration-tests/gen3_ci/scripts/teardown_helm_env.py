import os
import subprocess

from utils import logger

RELEASE_NAME = os.getenv("NAMESPACE")
NAMESPACE = os.getenv("NAMESPACE")
INSTANCE_TYPE = os.getenv("GEN3_INSTANCE_TYPE")

if __name__ == "__main__":
    with open("output/report.md", "r", encoding="utf-8") as file:
        content = file.read().lower()
    if (
        "failed" not in content
        and "error" not in content
        and INSTANCE_TYPE == "HELM_LOCAL"
    ) or (os.getenv("NAMESPACE") == "nightly-build"):
        # logger.info(f"Tearing down environment: {NAMESPACE}")
        # teardown_helm_environment()
        logger.info(f"Setting label teardown for environment: {NAMESPACE}")
        cmd = ["kubectl", "label", "namespace", NAMESPACE, "teardown=true"]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            logger.info(f"Set label teardown for environment: {NAMESPACE}")
        else:
            logger.info(result.stderr)
