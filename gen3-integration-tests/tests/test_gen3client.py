import datetime
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest
import utils.gen3_client_install as gc
from services.indexd import Indexd
from utils import logger


@pytest.mark.skipif(
    "indexd" not in pytest.deployed_services,
    reason="indexd service is not running on this environment",
)
@pytest.mark.skipif(
    "ssjdispatcher" not in pytest.deployed_services,
    reason="ssjdispatcher service is not running on this environment",
)
@pytest.mark.indexd
@pytest.mark.gen3_client
class TestGen3Client:
    @classmethod
    def setup_class(cls):
        get_go_path = subprocess.run(
            ["go env GOPATH"], shell=True, stdout=subprocess.PIPE
        )
        cls.go_path = get_go_path.stdout.decode("utf-8").strip()
        gc.install_gen3_client(cls.go_path)

    def test_gen3_client(self):
        """
        Scenario: Test Gen3-Client
        Steps:
            1. Install latest gen3-client executable and check the version
            2. Create a api key json file for the user
            3. Configure the Client with credfile and apiendpoint
            4. Upload the file via gen3-client and get the GUID from indexd
            5. Download the file with GUID via gen3-client
        """
        indexd = Indexd()
        gen3_path = "~/.gen3"
        guid = None
        user = "indexing_account"
        cred_json_file = f"{gen3_path}/{pytest.namespace}_{user}.json"
        profile = f"{pytest.namespace}_profile"

        # create a file that can be uploaded
        file_data = f"This is a test file uploaded via gen3-client test"
        current_time = datetime.datetime.now().strftime("%Y_%m_%d_%H_%S")
        file_name = f"file_{current_time}.txt"
        file_path = f"./{file_name}"
        with open(file_name, "w") as f:
            f.write(file_data)

        # Configuring the gen3-client
        logger.info(f"Configuring gen3-client profile {profile} ...")
        configure_client_cmd = [
            f"gen3-client configure --profile={profile} --cred={cred_json_file} --apiendpoint={pytest.root_url}"
        ]
        logger.info(f"Running gen3-client configure command : {configure_client_cmd}")
        configure = subprocess.run(configure_client_cmd, shell=True)
        if configure.returncode == 0:
            logger.info(f"Successfully configure profile {profile}")
        else:
            logger.info(f"Failed to configure profile {profile}")

        # Upload file via gen3-client
        logger.info(f"Uploading file via gen3-client ...")
        upload_cmd = [
            f"gen3-client upload --profile={profile} --upload-path={file_path}"
        ]
        logger.info(f"Running gen3-client upload command : {upload_cmd}")
        try:
            try:
                upload = subprocess.run(
                    upload_cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                logger.info(f"### Upload stdout is {upload.stdout.decode('utf-8')}")
                logger.info(f"### Upload stderr is {upload.stderr.decode('utf-8')}")
            except subprocess.CalledProcessError as e:
                logger.info(e)
            if upload.returncode == 0:
                regex_exp_pattern = r"to GUID\s*(.+)."
                guid_match = re.findall(
                    regex_exp_pattern, upload.stderr.decode("utf-8")
                )
                if guid_match:
                    guid = guid_match[0]
                    logger.info(f"Uploaded File GUID : {guid}")
        except Exception as e:
            logger.info(
                f"Upload error : Error occurred {type(e).__name__} and Error Message is {str(e)} "
            )

        # Adding explicit wait for indexing job pod to finish adding record metadata
        time.sleep(20)

        record = indexd.get_record(guid)
        rev = record.get("rev", None)

        # Create a temporary directory for downloading the file via gen3-client
        download_path = f"tmpDownload_{current_time}"
        os.mkdir(f"{download_path}/")
        os.chdir(f"{download_path}")

        logger.info(f"Downloading file via gen3-client ...")
        download_cmd = [
            f"gen3-client download-single --profile={profile} --guid={guid} --download-path={download_path}/ --no-prompt"
        ]
        logger.info(f"Running gen3-client download-single command : {download_cmd}")
        try:
            download = subprocess.run(
                download_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            logger.info(f"Download stdout is {download.stdout.decode('utf-8')}")
            logger.info(f"Download stderr is {download.stderr.decode('utf-8')}")
            if os.path.exists(download_path):
                logger.info(f"File {file_name} is downloaded successfully")
            else:
                logger.info(f"File {file_name} is not downloaded successfully")
        except Exception as e:
            logger.info(
                f"Download error : Error occurred {type(e).__name__} and Error Message is {str(e)} "
            )

        try:
            file_path = Path(f"{download_path}/{file_name}")
            if file_path.exists:
                logger.info(f"The downloaded file {file_name} exists")
        except FileNotFoundError:
            logger.info(f"The file {file_name} does not exist")

        # Delete the indexd record
        delete_record = indexd.delete_record_via_api(guid, rev)
        assert delete_record == 200, f"Failed to delete record {guid}"

        # Deleting the folder src from filesystem
        try:
            shutil.rmtree(f"{self.go_path}/src")
            logger.info(f"Folder src deleted successfully ...")
        except OSError as e:
            raise OSError(f"Error removing directory {self.go_path}/src: {e.message}")
