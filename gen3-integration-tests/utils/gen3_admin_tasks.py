import json
import os
import random
import string
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
import requests
from dotenv import load_dotenv
from utils import TEST_DATA_PATH_OBJECT, logger
from utils.misc import retry

load_dotenv()


@retry(times=5, delay=60, exceptions=(AssertionError))
def get_portal_config():
    """Fetch portal config from the GUI"""
    deployed_services = get_list_of_services_deployed()
    if "portal" not in deployed_services:
        return {}
    res = requests.get(f"{pytest.root_url_portal}/data/config/gitops.json")
    assert res.status_code == 200, f"Expected 200 but got {res.status_code}"
    return res.json()


def check_button_is_present(data, search_button):
    # Checks manifest download button for Register User tests
    for button in data:
        if search_button in button.get("type", "") and button.get("enabled"):
            return True
    return False


def validate_button_in_portal_config(data, search_button):
    if isinstance(data, dict):
        if "buttons" in data and check_button_is_present(
            data["buttons"], search_button
        ):
            if search_button == "export-to-pfb":
                return True
            if search_button == "manifest":
                return data["tabTitle"]
        for val in data.values():
            result = validate_button_in_portal_config(val, search_button)
            if result:
                return result
    elif isinstance(data, list):
        for item in data:
            result = validate_button_in_portal_config(item, search_button)
            if result:
                return result
    return False


def get_env_configurations(test_env_namespace: str = ""):
    """
    Fetch environment configs.
    Returns dict { file name: file contents }
    """
    cmd = [
        "kubectl",
        "-n",
        test_env_namespace,
        "get",
        "configmap",
        "manifest-global",
        "-o",
        "json",
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        jq_command = ["jq", "-r", ".data"]
        jq_result = subprocess.run(
            jq_command,
            input=result.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if jq_result.returncode == 0:
            return {"manifest.json": '{ "global": ' + jq_result.stdout + "}"}
        else:
            logger.info(f"Error in jq command: {jq_result.stderr}")
    else:
        logger.info(f"Error in kubectl command: {result.stderr}")


def run_gen3_job(
    job_name: str,
    test_env_namespace: str = "",
):
    """
    Run gen3 job (e.g., metadata-aggregate-sync).
    """
    # job_pod = f"{job_name}-{uuid.uuid4()}"
    cronjob_name = job_name
    if job_name == "etl":
        cronjob_name = "etl-cronjob"
    job_name += "-" + "".join(
        random.choices(string.ascii_lowercase + string.digits, k=4)
    )
    cmd = [
        "kubectl",
        "-n",
        test_env_namespace,
        "create",
        "job",
        f"--from=cronjob/{cronjob_name}",
        job_name,
    ]
    logger.info(cmd)
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        logger.info(f"{job_name} job triggered - {result.stdout.decode('utf-8')}")
    else:
        raise Exception(f"{job_name} failed to start - {result.stderr.decode('utf-8')}")
    check_job_pod(job_name=job_name, test_env_namespace=pytest.namespace)


def fence_delete_expired_clients():
    cmd = ["kubectl", "-n", pytest.namespace, "get", "pods", "-l", "app=fence"]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        fence_pod_name = result.stdout.splitlines()[-1].split()[0]
    else:
        raise Exception("Unable to retrieve fence-deployment pod")

    delete_explired_clients_cmd = [
        "kubectl",
        "exec",
        "-n",
        pytest.namespace,
        "-i",
        fence_pod_name,
        "--",
        "fence-create",
        "client-delete-expired",
    ]
    delete_explired_client_result = subprocess.run(
        delete_explired_clients_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    if not delete_explired_client_result.returncode == 0:
        logger.info(delete_explired_client_result.stderr)
        raise Exception("Unable to delete expired clients.")
    return delete_explired_client_result.stdout.strip()


def check_job_pod(
    job_name: str,
    test_env_namespace: str = "",
):
    cmd = [
        "kubectl",
        "-n",
        test_env_namespace,
        "wait",
        "--for=condition=complete",
        f"job/{job_name}",
        "--timeout=20m",
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        logger.info(f"Job {job_name} completed successfully")
    else:
        raise Exception(
            f"Job {job_name} failed to complete in 20 minutes. Info: {result.stderr.strip()}"
        )


@retry(times=2, delay=30, exceptions=(AssertionError,))
def _get_fence_pod_name(test_env_namespace):
    # Get the pod name for fence app
    cmd = ["kubectl", "-n", test_env_namespace, "get", "pods", "-l", "app=fence"]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    assert result.returncode == 0
    fence_pod_name = result.stdout.splitlines()[-1].split()[0]
    return fence_pod_name


def _get_delete_cmd(test_env_namespace, client_name):
    fence_pod_name = _get_fence_pod_name(test_env_namespace)
    return [
        "kubectl",
        "-n",
        test_env_namespace,
        "exec",
        "-i",
        fence_pod_name,
        "--",
        "fence-create",
        "client-delete",
        "--client",
        client_name,
    ]


def _get_create_cmd(
    test_env_namespace,
    arborist_policies,
    client_type,
    client_name,
    username,
    expires_in,
    scopes,
):
    hostname = os.getenv("HOSTNAME")
    fence_pod_name = _get_fence_pod_name(test_env_namespace)
    create_cmd = [
        "kubectl",
        "-n",
        test_env_namespace,
        "exec",
        "-i",
        fence_pod_name,
        "--",
        "fence-create",
    ]

    if arborist_policies:
        create_cmd = create_cmd + ["client-create", "--policies", arborist_policies]
    else:
        create_cmd = create_cmd + ["client-create"]

    if client_type == "client_credentials":
        create_cmd = create_cmd + [
            "--client",
            client_name,
            "--grant-types",
            "client_credentials",
        ]
    elif client_type == "implicit":
        create_cmd = create_cmd + [
            "--client",
            client_name,
            "--user",
            username,
            "--urls",
            f"https://{hostname}",
            "--grant-types",
            "implicit",
            "--public",
        ]
    elif client_type == "auth_code":
        create_cmd = create_cmd + [
            "--client",
            client_name,
            "--user",
            username,
            "--urls",
            f"https://{hostname}",
            "--grant-types",
            "authorization_code",
        ]
    else:
        create_cmd = create_cmd + [
            "--client",
            client_name,
            "--user",
            username,
            "--urls",
            f"https://{hostname}",
        ]

    if expires_in:
        create_cmd = create_cmd + ["--expires-in", expires_in]
    if scopes:
        create_cmd = create_cmd + ["--allowed-scopes"] + scopes.split(" ")
    return create_cmd


@retry(times=2, delay=30, exceptions=(subprocess.TimeoutExpired,))
def setup_fence_test_client(test_env_namespace, client_data):
    """
    Create fence test client
    """
    client_name, username, client_type, arborist_policies, expires_in, scopes = (
        client_data
    )

    logger.info(f"Creating fence client: {client_name}")

    # Delete existing client
    try:
        subprocess.run(
            _get_delete_cmd(test_env_namespace, client_name),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception:
        logger.info(f"Client {client_name} not present, deletion failed as expected.")

    # Create the client
    create_result = subprocess.run(
        _get_create_cmd(
            test_env_namespace,
            arborist_policies,
            client_type,
            client_name,
            username,
            expires_in,
            scopes,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
    )
    if create_result.returncode == 0:
        client_info = create_result.stdout.strip().split("\n")[-1]
    else:
        raise Exception(
            f"Unable to create client '{client_name}'. Response: {create_result.stderr.strip()}"
        )
    return (client_name, client_info)


def setup_fence_test_clients(
    clients_data: str,
    test_env_namespace: str = "",
):
    """
    Create fence clients
    """
    clients_file_path = TEST_DATA_PATH_OBJECT / "fence_clients" / "clients_creds.txt"
    rotated_clients_file_path = (
        TEST_DATA_PATH_OBJECT / "fence_clients" / "client_rotate_creds.txt"
    )
    # Create clients
    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_task = {
            executor.submit(setup_fence_test_client, test_env_namespace, client_data)
            for client_data in clients_data
        }
        for future in as_completed(future_to_task):
            results.append(future.result())
    with open(clients_file_path, "+a") as outfile:
        for result in results:
            outfile.write(f"{result[0]}:{result[1]}\n")

    # Rotate Client
    rotate_client_list = ["jenkins-client-tester"]
    for client in rotate_client_list:
        rotate_client_command = [
            "kubectl",
            "-n",
            test_env_namespace,
            "exec",
            "-i",
            _get_fence_pod_name(test_env_namespace),
            "--",
            "fence-create",
            "client-rotate",
            "--client",
            client,
        ]
        rotate_result = subprocess.run(
            rotate_client_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if rotate_result.returncode == 0:
            client_info = rotate_result.stdout.strip().split("\n")[-1]
        else:
            raise Exception(
                f"Unable to rotate client '{client}'. Response: {rotate_result.stderr.strip()}"
            )
        with open(rotated_clients_file_path, "+a") as outfile:
            outfile.write(f"{client}:{client_info}\n")


def delete_fence_client(clients_data: str, test_env_namespace: str = ""):
    """
    Delete client
    """
    # Get the pod name for fence app
    cmd = ["kubectl", "-n", test_env_namespace, "get", "pods", "-l", "app=fence"]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        fence_pod_name = result.stdout.splitlines()[-1].split()[0]
    else:
        raise Exception("Unable to retrieve fence-deployment pod")

    # Delete clients
    for line in clients_data.split("\n")[1:]:
        client_name = line.split(",")[0]
        logger.info(f"Deleting Client: {client_name}")

        # Delete existing client if it exists
        delete_cmd = [
            "kubectl",
            "-n",
            test_env_namespace,
            "exec",
            "-i",
            fence_pod_name,
            "--",
            "fence-create",
            "client-delete",
            "--client",
            client_name,
        ]
        subprocess.run(
            delete_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )


def revoke_arborist_policy(username: str, policy: str, test_env_namespace: str = ""):
    """
    Revoke arborist policy
    """
    cmd = [
        "kubectl",
        "-n",
        test_env_namespace,
        "get",
        "pods",
        "-l",
        "app=fence",
        "-o",
        "jsonpath='{.items[0].metadata.name}'",
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        fence_pod_name = result.stdout.strip().replace("'", "")
    else:
        raise Exception("Unable to retrieve fence-deployment pod")

    cmd = [
        "kubectl",
        "-n",
        test_env_namespace,
        "exec",
        "-i",
        fence_pod_name,
        "--",
        "curl",
        "-X",
        "DELETE",
        f"arborist-service/user/{username}/policy/{policy}",
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if not result.returncode == 0:
        raise Exception("Unable to revoke arborist policy")


def mutate_manifest_for_guppy_test(
    test_env_namespace: str = "", indexname: str = "jenkins"
):
    """
    Point guppy to preferred indices
    """
    # Command to get guppy config map
    get_guppy_cm = f"kubectl -n {test_env_namespace} get cm manifest-guppy -o yaml > original_guppy_config.yaml"
    get_guppy_cm_result = subprocess.run(
        get_guppy_cm,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        text=True,
    )
    if not get_guppy_cm_result.returncode == 0:
        raise Exception("Unable to get guppy confi map")
    # If indexname is set to jenkins set guppy config to default ci based changes
    if indexname == "jenkins":
        cmd_list = [
            'sed -i \'s/"index":"[^"]*_subject"/"index":"\'ci_subject_alias\'"/\' original_guppy_config.yaml',
            'sed -i \'s/"index":"[^"]*_file"/"index":"\'ci_file_alias\'"/\' original_guppy_config.yaml',
            'sed -i \'s/"config_index": "[^"]*config"/"config_index": "\'ci_configs_alias\'"/\' original_guppy_config.yaml',
        ]
        for cmd in cmd_list:
            cmd_result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                text=True,
            )
            if not cmd_result.returncode == 0:
                raise Exception(f"Unable to execute {cmd}")
    # If indexname is not set to jenkins set guppy config to manifest based changes
    else:
        cmd_list = [
            f"kubectl -n {test_env_namespace} get cm etl-mapping -o jsonpath='{{.data.etlMapping\\.yaml}}' > etlMapping.yaml",
            'sed -i \'s/"index":"[^"]*_subject_alias"/"index":"\'$(yq \'.mappings[].name\' etlMapping.yaml | grep subject)\'"/\' original_guppy_config.yaml',
            'sed -i \'s/"index":"[^"]*_file_alias"/"index":"\'$(yq \'.mappings[].name\' etlMapping.yaml | grep -v index_file |grep file)\'"/\' original_guppy_config.yaml',
        ]
        for cmd in cmd_list:
            logger.info(f"Executing command: {cmd}")
            cmd_result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                text=True,
            )
            if not cmd_result.returncode == 0:
                raise Exception(f"Unable to execute {cmd}")
    # Run commands to set new guppy config and clear up files
    cmd_list = [
        f"kubectl -n {test_env_namespace} delete configmap manifest-guppy",
        f"kubectl -n {test_env_namespace} apply -f original_guppy_config.yaml",
        f"kubectl -n {test_env_namespace} rollout restart deployment/guppy-deployment",
        f"kubectl -n {test_env_namespace} rollout status deployment/guppy-deployment --timeout=5m",
        "cat original_guppy_config.yaml",
        "rm -rf original_guppy_config.yaml",
    ]
    for cmd in cmd_list:
        cmd_result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            text=True,
        )
        if not cmd_result.returncode == 0:
            raise Exception(f"Unable to execute {cmd}")


def clean_up_indices(test_env_namespace: str = ""):
    """
    Clean up indices before running the ETL tests
    """
    kubectl_port_forward_process = subprocess.Popen(
        [
            "kubectl",
            "port-forward",
            "service/gen3-elasticsearch-master",
            "9200:9200",
            "-n",
            test_env_namespace,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for i in range(6):
        line = kubectl_port_forward_process.stdout.readline().decode("utf-8").strip()
        if "Forwarding from" in line:
            break
        time.sleep(5)
    get_alias_cmd = (
        "kubectl -n "
        + test_env_namespace
        + " get cm etl-mapping -o jsonpath='{.data.etlMapping\.yaml}' | yq '.mappings[].name' | xargs"
    )
    get_alias_result = subprocess.run(
        get_alias_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        text=True,
    )
    if not get_alias_result.returncode == 0:
        raise Exception(
            f"Unable to get alias. Error: {get_alias_result.stderr.strip()}"
        )
    logger.info(f"Stderr: {get_alias_result.stderr.strip()}")
    logger.info(f"List of aliases: {get_alias_result.stdout.strip()}")
    for alias_name in get_alias_result.stdout.strip().split(" "):
        get_indices_cmd = [
            "curl",
            "-s",
            f"http://localhost:9200/_cat/indices/{alias_name}*?h=index",
        ]
        logger.info(get_indices_cmd)
        get_indices_result = subprocess.run(
            get_indices_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if not get_indices_result.returncode == 0:
            raise Exception(
                f"Unable to get indices code for {alias_name}. Error: {get_indices_result.stderr.strip()}"
            )

        indices = get_indices_result.stdout.strip().split("\n")
        indices = [i for i in indices if i]
        for index_name in indices:
            delete_indices_cmd = [
                "curl",
                "-X",
                "DELETE",
                f"localhost:9200/{index_name}",
            ]
            delete_indices_result = subprocess.run(
                delete_indices_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if not delete_indices_result.returncode == 0:
                raise Exception(
                    f"Unable to delete index {alias_name}. Error: {delete_indices_result.stderr.strip()}"
                )
    os.kill(kubectl_port_forward_process.pid, 9)  # Send SIGKILL to the process
    kubectl_port_forward_process.wait()


def check_indices_after_etl(test_env_namespace: str):
    """
    Check indices after running the ETL tests
    """
    kubectl_port_forward_process = subprocess.Popen(
        [
            "kubectl",
            "port-forward",
            "service/gen3-elasticsearch-master",
            "9200:9200",
            "-n",
            test_env_namespace,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for i in range(6):
        line = kubectl_port_forward_process.stdout.readline().decode("utf-8").strip()
        if "Forwarding from" in line:
            break
        time.sleep(5)
    get_alias_cmd = (
        "kubectl -n "
        + test_env_namespace
        + " get cm etl-mapping -o jsonpath='{.data.etlMapping\.yaml}' | yq '.mappings[].name' | xargs"
    )
    get_alias_result = subprocess.run(
        get_alias_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        text=True,
    )
    if not get_alias_result.returncode == 0:
        raise Exception(
            f"Unable to get alias. Error: {get_alias_result.stderr.strip()}"
        )
    logger.info(f"Stderr: {get_alias_result.stderr.strip()}")
    logger.info(f"List of aliases: {get_alias_result.stdout.strip()}")
    for alias_name in get_alias_result.stdout.strip().split(" "):
        get_alias_status_cmd = [
            "curl",
            "-I",
            "-s",
            f"localhost:9200/_alias/{alias_name}",
        ]
        get_alias_status_result = subprocess.run(
            get_alias_status_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if not get_alias_status_result.returncode == 0:
            raise Exception(
                f"Unable to get status code for {alias_name}. Error: {get_alias_status_result.stderr.strip()}"
            )
        assert (
            "200 OK" in get_alias_status_result.stdout.strip()
        ), f"Expected 200 OK but got {get_alias_status_result.stdout.strip()} for {alias_name}"
        logger.info(f"{alias_name} is present")

        get_indices_name_cmd = [
            "curl",
            "-X",
            "GET",
            "-s",
            f"localhost:9200/_alias/{alias_name}",
        ]
        get_indices_name_result = subprocess.run(
            get_indices_name_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if not get_indices_name_result.returncode == 0:
            raise Exception(
                f"Unable to get status code for {alias_name}. Error: {get_indices_name_result.stderr.strip()}"
            )
        data = json.loads(get_indices_name_result.stdout.strip())
        indices_name = list(data.keys())[0]
        version = indices_name.split("_")[-1]
        if version == "1":
            logger.info(f"Index version has increased for {alias_name}")
        else:
            logger.info(data)
            raise Exception(f"Index version has not increased for {alias_name}")
    os.kill(kubectl_port_forward_process.pid, 9)  # Send SIGKILL to the process
    kubectl_port_forward_process.wait()


def check_indices_etl_version(test_env_namespace: str):
    """
    Check indices etl version
    """
    kubectl_port_forward_process = subprocess.Popen(
        [
            "kubectl",
            "port-forward",
            "service/gen3-elasticsearch-master",
            "9200:9200",
            "-n",
            test_env_namespace,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    for i in range(6):
        line = kubectl_port_forward_process.stdout.readline().decode("utf-8").strip()
        if "Forwarding from" in line:
            break
        time.sleep(5)
    get_alias_cmd = (
        "kubectl -n "
        + test_env_namespace
        + " get cm etl-mapping -o jsonpath='{.data.etlMapping\.yaml}' | yq '.mappings[].name' | xargs"
    )
    get_alias_result = subprocess.run(
        get_alias_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        text=True,
    )
    if not get_alias_result.returncode == 0:
        raise Exception(
            f"Unable to get alias. Error: {get_alias_result.stderr.strip()}"
        )
    logger.info(f"Stderr: {get_alias_result.stderr.strip()}")
    logger.info(f"List of aliases: {get_alias_result.stdout.strip()}")
    indices_versions = {}
    for alias_name in get_alias_result.stdout.strip().split(" "):
        get_alias_status_cmd = [
            "curl",
            "-I",
            "-s",
            f"localhost:9200/_alias/{alias_name}",
        ]
        get_alias_status_result = subprocess.run(
            get_alias_status_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        logger.info(get_alias_status_result.stdout.strip())
        if "404 Not Found" in get_alias_status_result.stdout.strip():
            logger.info(
                f"Unable to get status code for {alias_name}. Error: {get_alias_status_result.stdout.strip()}"
            )
            indices_versions[alias_name] = -1
        else:
            assert (
                "200 OK" in get_alias_status_result.stdout.strip()
            ), f"Expected 200 OK but got {get_alias_status_result.stdout.strip()} for {alias_name}"
            logger.info(f"{alias_name} is present")

            get_indices_name_cmd = [
                "curl",
                "-X",
                "GET",
                "-s",
                f"localhost:9200/_alias/{alias_name}",
            ]
            get_indices_name_result = subprocess.run(
                get_indices_name_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if not get_indices_name_result.returncode == 0:
                raise Exception(
                    f"Unable to get status code for {alias_name}. Error: {get_indices_name_result.stderr.strip()}"
                )
            data = json.loads(get_indices_name_result.stdout.strip())
            indices_name = list(data.keys())[0]
            version = indices_name.split("_")[-1]
            indices_versions[alias_name] = int(version)
    os.kill(kubectl_port_forward_process.pid, 9)  # Send SIGKILL to the process
    kubectl_port_forward_process.wait()
    return indices_versions


def create_access_token(expired, username, test_env_namespace: str = ""):
    """
    Create access token
    """
    # Get the pod name for fence app
    cmd = ["kubectl", "-n", test_env_namespace, "get", "pods", "-l", f"app=fence"]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        fence_pod_name = result.stdout.splitlines()[-1].split()[0]
    else:
        raise Exception("Unable to retrieve fence-deployment pod")

    cmd = [
        "kubectl",
        "exec",
        "-n",
        test_env_namespace,
        "-i",
        fence_pod_name,
        "--",
        "fence-create",
        "token-create",
        "--scopes",
        "openid,user,fence,data,credentials,google_service_account,google_credentials",
        "--type",
        "access_token",
        "--exp",
        expired,
        "--username",
        username,
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        return result.stdout.strip()
    else:
        logger.info(result.stderr)
        raise Exception("Unable to get expired access_token")


def create_link_google_test_buckets(test_env_namespace: str = ""):
    """
    Execute command for creating and linking Google test buckets
    """
    cmd = ["kubectl", "-n", test_env_namespace, "get", "pods", "-l", "app=fence"]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        fence_pod_name = result.stdout.splitlines()[-1].split()[0]
    else:
        raise Exception("Unable to retrieve fence-deployment pod")
    bukcet_info = {"dcf-integration-qa": "QA", "dcf-integration-test": "test"}
    for bucket_name in bukcet_info.keys():
        create_bucket_cmd = [
            "kubectl",
            "-n",
            test_env_namespace,
            "exec",
            "-i",
            fence_pod_name,
            "--",
            "fence-create",
            "google-bucket-create",
            "--unique-name",
            bucket_name,
            "--google-project-id",
            "dcf-integration",
            "--project-auth-id",
            bukcet_info[bucket_name],
            "--public",
            "False",
        ]
        create_bucket_result = subprocess.run(
            create_bucket_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if create_bucket_result.returncode == 0:
            logger.info(f"Created bucket: {bucket_name}")
        else:
            raise Exception(f"Unable to create google bucket for {bucket_name}")
    phs_info = {
        "phs000179": "dcf-integration-qa",
        "phs000178": "dcf-integration-test",
        "phs001194": "dcf-integration-test",
        "phs000571": "dcf-integration-test",
    }
    for phs in phs_info.keys():
        link_phs_cmd = [
            "kubectl",
            "-n",
            test_env_namespace,
            "exec",
            "-i",
            fence_pod_name,
            "--",
            "fence-create",
            "link-bucket-to-project",
            "--project_auth_id",
            phs,
            "--bucket_id",
            phs_info[phs],
            "--bucket_provider",
            "google",
        ]
        link_phs_result = subprocess.run(
            link_phs_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if link_phs_result.returncode == 0:
            logger.info(f"Created link: {phs}")
        else:
            raise Exception(f"Unable to create google bucket for {bucket_name}")


def get_list_of_services_deployed():
    cmd = [
        "kubectl",
        "-n",
        pytest.namespace,
        "get",
        "deployments",
        "-o=jsonpath='{range .items[*]}{.metadata.name}{\"\\n\"}{end}'",
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        return result.stdout.strip().replace("'", "")
    else:
        raise Exception("Unable to retrieve deployed services")


def get_enabled_sower_jobs():
    cmd = [
        "kubectl",
        "-n",
        pytest.namespace,
        "get",
        "cm",
        "manifest-sower",
        "-o=jsonpath='{.data.json}'",
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        return result.stdout.strip().replace("'", "")
    else:
        return []


def is_agg_mds_enabled():
    cmd = (
        "kubectl describe deployment metadata-deployment -n "
        + pytest.namespace
        + " | grep USE_AGG_MDS"
    )
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True
    )
    if result.returncode == 0:
        if "True" in result.stdout.strip():
            return True
    return False


def check_indexs3client_job_deployed():
    cmd = [
        "kubectl",
        "-n",
        pytest.namespace,
        "get",
        "cm",
        "manifest-ssjdispatcher",
        "-o=jsonpath='{.data.job_images}'",
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0 and "indexs3client" in result.stdout.strip():
        return True
    else:
        return False


def is_google_enabled():
    cmd = [
        "kubectl",
        "-n",
        pytest.namespace,
        "get",
        "cm",
        "manifest-global",
        "-o=jsonpath='{.data}'",
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        metadata_output = json.loads(result.stdout.strip().replace("'", ""))
        if metadata_output.get("google_enabled", "").lower() == "true":
            return True
        else:
            return False
    else:
        return False


def skip_portal_tests():
    deployed_services = get_list_of_services_deployed()
    if "data-ecosystem-portal" in deployed_services:
        return True
    if "dataguids" in deployed_services:
        return True
    if "portal" not in deployed_services:
        return True
    return False


def is_register_user_enabled(test_env_namespace: str = ""):
    cmd = (
        "kubectl get cm manifest-fence -o yaml -n "
        + test_env_namespace
        + " | grep REGISTER_USERS_ON"
    )
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True
    )
    if result.returncode == 0:
        if "true" in result.stdout.strip():
            return True
    return False
