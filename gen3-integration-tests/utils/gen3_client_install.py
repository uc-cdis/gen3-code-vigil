import os
import subprocess

from pathlib import Path

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def install_gen3_client(path):
    # Installing the gen3-client executable
    logger.info(f"#### goPath: {path}")
    # Check if the gen3-client folder exists in GOPATH
    os.chdir(f"{path}")
    Path(f"{path}/src/github.com/uc-cdis/").mkdir(mode=777, parents=True, exist_ok=True)
    os.chmod(f"{path}/src/github.com/uc-cdis", int("777", base=8))
    os.chdir(f"{path}/src/github.com/uc-cdis/")
    subprocess.run(
        ["git clone https://github.com/uc-cdis/cdis-data-client.git"], shell=True
    )
    os.rename("cdis-data-client", "gen3-client")
    if os.path.exists(f"{path}/src/github.com/uc-cdis/gen3-client")
        os.chdir("gen3-client/")
        logger.info("Changed directory to gen3-client/")
    else
        logger.info("Directory cdis-data-client not found")
    subprocess.run(["go get -d ./..."], shell=True)
    subprocess.run(["go install ."], shell=True)

    logger.info(f"gen3-client installation completed.")
    # After installation, changing to directory where gen3-client is installed
    os.chdir(f"{path}/bin")
    # Move the gen3-client executable to ~/.gen3 folder
    subprocess.call(["mv gen3-client ~/.gen3"], shell=True)

    # Verify the gen3-client is properly installed
    version = subprocess.run(["gen3-client"], shell=True, stdout=subprocess.PIPE)
    logger.info(f"### {version.stdout.decode('utf-8').strip()}")
