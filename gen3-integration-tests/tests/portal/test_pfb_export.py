import pytest
import subprocess
import datetime
import time
import utils.gen3_client_install as gc
import utils.gen3_admin_tasks as gat

from gen3.auth import Gen3Auth
from services.graph import GraphDataTools
from utils.test_execution import screenshot
from services.indexd import Indexd

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.tube
class TestPFBExport(object):
    variables = {}

    @classmethod
    def setup_class(cls):
        logger.info("Setup")

        # handling the targetMappingNode
        # submitted_unaligned_reads is set by default in pretty much every dictionary
        cls.variables["target_mapping_node"] = (
            "sequencing"
            if "anvil" in pytest.namespace
            else "unaligned_reads_file"
            if "vpodc" in pytest.namespace
            else "submitted_unaligned_reads"
        )

        # Restore original etl-mapping and manifest-guppy configmaps
        logger.info(
            "Running kube-setup-guppy to restore any configmaps that have been mutated. This can take a couple of mins..."
        )
        gat.run_gen3_job(pytest.namespace, "kube-setup-guppy")

        # getting go_path to install gen3-client
        get_go_path = subprocess.run(
            ["go env GOPATH"], shell=True, stdout=subprocess.PIPE
        )
        cls.variables["get_go_path"] = get_go_path

    def teardown_class(cls):
        # logger.info("Teardown - Clean up Indices and kube-setup-guppy")
        # logger.info("Cleaning up indices created from ETL run")
        # gat.clean_up_indices(pytest.namespace)

        logger.info(
            "Running kube-setup-guppy to restore any configmaps that have been mutated. This can take a couple of mins..."
        )
        gat.run_gen3_job(pytest.namespace, "kube-setup-guppy")

    def generate_data_and_upload(self):
        """
        Scenario: Test PFB Export
        Steps:
            1. Submit dummy data to the Gen3 Commons environment
            2. Upload a file through the gen3-client CLI
            3. Map the uploaded file to one of the subjects of the dummy dataset
            4. Mutate etl-mapping config and run ETL to create new indices in elastic search
            5. Mutate manifest-guppy config and roll guppy so the recently-submitted dataset will be available on the Explorer page
            6. Visit the Explorer page, select a cohort, export to PFB and download the .avro file
            7. Install the latest pypfb CLI version and make sure we can parse the avro file
        """
        indexd = Indexd()
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sd_tools = GraphDataTools(auth=auth)

        # generating random data with target_mapping_node
        gat.generate_test_data(
            pytest.namespace,
            pytest.users["main_account"],
            1,
            self.variables["target_mapping_node"],
        )

        # querying based on the graph node utilized for file mapping
        query_string = f'query {{ {self.variables["target_mapping_node"]} (first: 20, project_id: "DEV-test", quick_search: "", order_by_desc: "updated_datetime") {{id, type, submitter_id}} }}'
        variables = None

        received_data = sd_tools.graphql_query(query_string, variables)
        logger.info(f"received data: {received_data}")

        # install gen3-client
        gc.install_gen3_client(self.variables["get_go_path"])
        cred_json_file = f"~/.gen3/{pytest.namespace}_main_account.json"
        profile = f"{pytest.namespace}_profile"
        # configuring profile via gen3-client
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
        # create a file that can be uploaded
        file_data = (
            f"This is a test file uploaded via gen3-client test for PFBExport Test"
        )
        current_time = datetime.datetime.now().strftime("%Y_%m_%d_%H_%S")
        file_name = f"file_{current_time}.txt"
        file_path = f"./{file_name}"
        with open(file_name, "w") as f:
            f.write(file_data)
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
        logger.info(f"{record}")
