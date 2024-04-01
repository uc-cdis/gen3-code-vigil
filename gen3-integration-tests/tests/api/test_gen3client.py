import subprocess
import os
import pytest
import datetime
import re
import shutil
import time

from services.indexd import Indexd

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.indexd
@pytest.mark.gen3_client
class TestGen3Client:
    @classmethod
    def setup_class(cls):
        # Installing the gen3-client executable
        get_go_path = subprocess.run(
            ["go env GOPATH"], shell=True, stdout=subprocess.PIPE
        )
        cls.go_path = get_go_path.stdout.decode("utf-8").strip()
        logger.info(f"#### goPath: {cls.go_path}")
        # Check if the gen3-client folder exists in GOPATH
        os.chdir(f"{cls.go_path}")
        os.makedirs(f"{cls.go_path}/src/github.com/", exist_ok=True)
        os.chmod(f"{cls.go_path}/src/github.com", int("777", base=8))
        os.makedirs(f"{cls.go_path}/src/github.com/uc-cdis/", exist_ok=True)
        os.chmod(f"{cls.go_path}/src/github.com/uc-cdis", int("777", base=8))
        os.chdir(f"{cls.go_path}/src/github.com/uc-cdis/")
        subprocess.run(
            ["git clone git@github.com:uc-cdis/cdis-data-client.git"], shell=True
        )
        subprocess.call(["mv cdis-data-client gen3-client"], shell=True)
        os.chdir("gen3-client")
        subprocess.run(["go get -d ./..."], shell=True)
        subprocess.run(["go install ."], shell=True)

        logger.info(f"gen3-client installation completed.")
        # After installation, changing to directory where gen3-client is installed
        os.chdir(f"{cls.go_path}/bin")
        # Move the gen3-client executable to ~/.gen3 folder
        subprocess.call(["mv gen3-client ~/.gen3"], shell=True)
        # Checking the version of gen3-client
        # 1. Verify the gen3-client is properly installed
        # 2. Check the version of gen3-client (NOTE:you always download latest version of gen3-client)
        version = subprocess.run(["gen3-client -v"], shell=True, stdout=subprocess.PIPE)
        logger.info(f"### {version.stdout.decode('utf-8').strip()}")

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
                logger.debug(f"### Upload stdout is {upload.stdout.decode('utf-8')}")
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

        indexd.get_files(guid)

        # # Create a temporary directory for downloading the file via gen3-client
        download_path = f"tmpDownload_{current_time}"
        os.mkdir(f"{download_path}/")
        os.chmod(f"{download_path}", int("777", base=8))

        logger.info(f"Downloading file via gen3-client ...")
        download_cmd = [
            f"gen3-client download-single --profile={profile} --guid={guid} --download-path={download_path}/ --no-prompt"
        ]
        logger.debug(f"Running gen3-client download-single command : {download_cmd}")
        try:
            download = subprocess.run(
                download_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            logger.info(f"Download stdout is {download.stdout.decode('utf-8')}")
            if os.path.exists(download_path):
                logger.info(f"File {download_path} is downloaded successfully")
            else:
                logger.info(f"File {download_path} is not downloaded successfully")
        except Exception as e:
            logger.info(
                f"Download error : Error occurred {type(e).__name__} and Error Message is {str(e)} "
            )

        # Delete the indexd record
        indexd.delete_files(guid)

        # Delete the file to be uploaded from {go_path}/bin
        os.remove(f"{file_name}")

        # Deleting the folder src from filesystem
        try:
            shutil.rmtree(f"{self.go_path}/src")
            logger.info(f"Folder src deleted successfully ...")
        except OSError as e:
            raise OSError(f"Error removing directory {self.go_path}/src: {e.message}")
