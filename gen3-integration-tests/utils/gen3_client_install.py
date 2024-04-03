import os
import subprocess

from pathlib import Path

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def install_gen3_client():
    # Installing the gen3-client executable
    get_go_path = subprocess.run(["go env GOPATH"], shell=True, stdout=subprocess.PIPE)
    go_path = get_go_path.stdout.decode("utf-8").strip()
    logger.info(f"#### goPath: {go_path}")
    # Check if the gen3-client folder exists in GOPATH
    os.chdir(f"{go_path}")
    Path(f"{go_path}/src/github.com/uc-cdis/").mkdir(
        mode=777, parents=True, exist_ok=True
    )
    # os.makedirs(f"{go_path}/src/github.com/", exist_ok=True)
    # os.chmod(f"{go_path}/src/github.com", int("777", base=8))
    # os.makedirs(f"{go_path}/src/github.com/uc-cdis/", exist_ok=True)
    os.chmod(f"{go_path}/src/github.com/uc-cdis", int("777", base=8))
    os.chdir(f"{go_path}/src/github.com/uc-cdis/")
    subprocess.run(
        ["git clone git@github.com:uc-cdis/cdis-data-client.git"], shell=True
    )
    subprocess.call(["mv cdis-data-client gen3-client"], shell=True)
    os.chdir("gen3-client")
    subprocess.run(["go get -d ./..."], shell=True)
    subprocess.run(["go install ."], shell=True)

    logger.info(f"gen3-client installation completed.")
    # After installation, changing to directory where gen3-client is installed
    os.chdir(f"{go_path}/bin")
    # Move the gen3-client executable to ~/.gen3 folder
    subprocess.call(["mv gen3-client ~/.gen3"], shell=True)

    # Verify the gen3-client is properly installed
    version = subprocess.run(["gen3-client"], shell=True, stdout=subprocess.PIPE)
    logger.info(f"### {version.stdout.decode('utf-8').strip()}")
