import json
import os
import pytest
import requests
import subprocess
import time
import uuid

from dotenv import load_dotenv

from utils import logger
from utils.jenkins import JenkinsJob
from utils import TEST_DATA_PATH_OBJECT

load_dotenv()


def get_portal_config():
    """Fetch portal config from the GUI"""
    if "heal" in pytest.tested_env:
        res = requests.get(f"{pytest.root_url}/portal/data/config/gitops.json")
    else:
        res = requests.get(f"{pytest.root_url}/data/config/gitops.json")
    if res.status_code == 200:
        return res.json()
    else:
        raise Exception(
            f"Unable to get portal config: status code {res.status_code} - response {res.text}"
        )


def get_kube_namespace(hostname: str = ""):
    """
    Compute the kubernetes namespace
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        return hostname.split(".")[0]
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        # TODO: Set up the namespace in helm deployment and use it like below. For now just use hostname
        #     cmd = (
        #         "kubectl get configmap manifest-global -o json | jq -r '.data.environment'"
        #     )
        #     result = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
        #     return result.stdout.decode("utf-8")
        return hostname


def get_env_configurations(test_env_namespace: str = ""):
    """
    Fetch configs that require adminvm interaction using jenkins.
    Returns dict { file name: file contents }
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        assert test_env_namespace != ""
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-fetch-configs",
        )
        params = {"NAMESPACE": test_env_namespace}
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return {
                    "manifest.json": job.get_artifact_content(
                        build_num, "manifest.json"
                    ),
                }
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        cmd = "kubectl get configmap manifest-global -o json | jq -r '.data'"
        result = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
        return {"manifest.json": '{ "global": ' + result.stdout.decode("utf-8") + "}"}


def run_gen3_command(test_env_namespace: str, command: str, roll_all: bool = False):
    """
    Run gen3 command (e.g., gen3 --help).
    Since this requires adminvm interaction we use jenkins.
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-run-gen3-command",
        )
        params = {
            "NAMESPACE": test_env_namespace,
            "COMMAND": command,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return job.get_build_result(build_num)
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        pass


def run_usersync(test_env_namespace: str, command: str, DBGAP_TRUE=False):
    """
    Run Usersync
    Since this requires adminvm interaction we use jenkins.
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-run-gen3-command",
        )
        if DBGAP_TRUE:
            command = f"{command} ADD_DBGAP true"
        params = {
            "NAMESPACE": test_env_namespace,
            "COMMAND": command,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return job.get_build_result(build_num)
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        cmd = "kubectl delete job usersync"
        result = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
        cmd = "kubectl create job --from=cronjob/usersync usersync"
        result = subprocess.run(cmd, stdout=subprocess.PIPE, shell=True)
        if not result.returncode == 0:
            raise Exception(f"Unable to run command. Got {result.stdout.strip()}")


def run_gen3_job(
    job_name: str,
    cmd_line_params: str = "",
    test_env_namespace: str = "",
    roll_all: bool = False,
):
    """
    Run gen3 job (e.g., metadata-aggregate-sync).
    Since this requires adminvm interaction we use jenkins.
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-run-gen3-job",
        )
        params = {
            "NAMESPACE": test_env_namespace,
            "JOB_NAME": job_name,
            "CMD_LINE_PARAMS": cmd_line_params,
            "GEN3_ROLL_ALL": roll_all,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return job.get_build_result(build_num)
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        job_pod = f"{job_name}-{uuid.uuid4()}"
        cmd = ["kubectl", "create", "job", f"--from=cronjob/{job_name}", job_pod]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            logger.info(f"{job_name} job triggered - {result.stdout.decode('utf-8')}")
        else:
            raise Exception(
                f"{job_name} failed to start - {result.stderr.decode('utf-8')}"
            )


def check_job_pod(
    test_env_namespace: str,
    job_name: str,
    label_name: str,
    expect_failure: bool = False,
):
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-check-kube-job-pod",
        )
        params = {
            "NAMESPACE": test_env_namespace,
            "JOB_NAME": job_name,
            "LABEL_NAME": label_name,
            "EXPECT_FAILURE": expect_failure,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return {"logs.txt": job.get_artifact_content(build_num, "logs.txt")}
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        # Wait for the job pod to start
        cmd = [
            "kubectl",
            "get",
            "pods",
            f"--selector=job-name={job_name}",
            "-o",
            "jsonpath='{.items[0].status.phase}'",
        ]
        i = 0
        job_started = False
        for i in range(6):
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.stdout.decode("utf-8").replace("'", "") in [
                "Running",
                "Succeeded",
                "Failed",
                "Completed",
            ]:
                job_started = True
                break
            else:
                time.sleep(10)
        if job_started is False:
            raise Exception(f"Pod failed to start for job {job_name}")

        # Wait for the job to complete
        cmd = [
            "kubectl",
            "get",
            "job",
            job_name,
            "-o",
            "jsonpath='{.status.conditions[?(@.type==\"Complete\")].status}'",
        ]
        job_completed = False
        for i in range(40):
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.stdout.decode("utf-8").replace("'", "") == "True":
                job_completed = True
                break
            else:
                time.sleep(30)
        if job_completed is False:
            raise Exception(f"Job {job_name} failed to complete in 20 minutes")


def setup_fence_test_clients(
    test_env_namespace: str,
    clients_data: str,
):
    """
    Runs jenkins job to create a fence client
    Since this requires adminvm interaction we use jenkins.
    """
    clients_file_path = TEST_DATA_PATH_OBJECT / "fence_clients" / "clients_creds.txt"
    rotated_clients_file_path = (
        TEST_DATA_PATH_OBJECT / "fence_clients" / "client_rotate_creds.txt"
    )
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-setup-fence-test-clients",
        )
        params = {
            "NAMESPACE": test_env_namespace,
            "CLIENTS_DATA": clients_data,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                with open(clients_file_path, "+a") as outfile:
                    outfile.write(
                        job.get_artifact_content(build_num, "clients_creds.txt")
                    )
                with open(rotated_clients_file_path, "+a") as outfile:
                    outfile.write(
                        job.get_artifact_content(build_num, "client_rotate_creds.txt")
                    )
            else:
                raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        hostname = os.getenv("HOSTNAME")

        # Get the pod name for fence app
        cmd = "kubectl get pods -l app=fence | awk '{{print $1}}' | tail -n 1"
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True
        )
        if result.returncode == 0:
            fence_pod_name = result.stdout.strip()
        else:
            raise Exception("Unable to retrieve fence-deployment pod")

        # Create clients
        for line in clients_data.split("\n")[1:]:
            (
                client_name,
                username,
                client_type,
                arborist_policies,
                expires_in,
                scopes,
            ) = line.split(",")
            logger.info(f"Creating Client: {client_name}")

            # Delete existing client if it exists
            delete_cmd = f"kubectl exec -it {fence_pod_name} -- fence-create client-delete --client {client_name}"
            subprocess.run(
                delete_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                text=True,
            )

            create_cmd = f"kubectl exec -it {fence_pod_name} -- fence-create"

            if arborist_policies:
                create_cmd = (
                    f"{create_cmd} client-create --policies {arborist_policies}"
                )
            else:
                create_cmd = f"{create_cmd} client-create"

            if client_type == "client_credentials":
                create_cmd = f"{create_cmd} --client {client_name} --grant-types client_credentials"
            elif client_type == "implicit":
                create_cmd = f"{create_cmd} --client {client_name} --user {username} --urls 'https://{hostname}' --grant-types implicit --public"
            elif client_type == "auth_code":
                create_cmd = f"{create_cmd} --client {client_name} --user {username} --urls 'https://{hostname}' --grant-types authorization_code"
            else:
                create_cmd = f"{create_cmd} --client {client_name} --user {username} --urls 'https://{hostname}'"

            if expires_in:
                create_cmd = f"{create_cmd} --expires-in {expires_in}"
            if scopes:
                create_cmd = f"{create_cmd} --allowed-scopes {scopes}"

            create_result = subprocess.run(
                create_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                text=True,
            )
            if result.returncode == 0:
                client_info = create_result.stdout.strip().split("\n")[-1]
            else:
                raise Exception(
                    f"Unable to create client for {client_name}. Response: {create_result.stderr.strip()}"
                )
            with open(clients_file_path, "+a") as outfile:
                outfile.write(f"{client_name}:{client_info}\n")

        # Rotate Client
        rotate_client_list = ["jenkins-client-tester"]
        for client in rotate_client_list:
            rotate_client_command = f"kubectl exec -it {fence_pod_name} -- fence-create client-rotate --client {client}"
            rotate_result = subprocess.run(
                rotate_client_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                text=True,
            )
            if rotate_result.returncode == 0:
                client_info = rotate_result.stdout.strip().split("\n")[-1]
            else:
                raise Exception(
                    f"Unable to create client for {client}. Response: {rotate_result.stderr.strip()}"
                )
            with open(rotated_clients_file_path, "+a") as outfile:
                outfile.write(f"{client}:{client_info}\n")


def force_link_google(test_env_namespace: str, username: str, email: str):
    """
    Runs jenkins job to force link google account
    Since this requires adminvm interaction we use jenkins.
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-fence-force-link-google",
        )
        params = {"NAMESPACE": test_env_namespace, "USERNAME": username, "EMAIL": email}
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return job.get_build_result(build_num)
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        pass


def delete_fence_client(test_env_namespace: str):
    """
    Runs jenkins job to delete client
    Since this requires adminvm interaction we use jenkins.
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-fence-delete-client",
        )
        params = {
            "NAMESPACE": test_env_namespace,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return job.get_build_result(build_num)
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        pass


def revoke_arborist_policy(test_env_namespace: str, username: str, policy: str):
    """
    Runs jenkins job to revoke arborist policy
    Since jenkins job is faster way without too much configuration changes
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-revoke-arborist-policy",
        )
        params = {
            "NAMESPACE": test_env_namespace,
            "USERNAME": username,
            "POLICY": policy,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return job.get_build_result(build_num)
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        pass


def update_audit_service_logging(test_env_namespace: str, audit_logging: str):
    """
    Runs jenkins job to enable/disable audit logging
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-audit-service-logging",
        )
        params = {
            "AUDIT_LOGGING": audit_logging,
            "NAMESPACE": test_env_namespace,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return True
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        pass


def mutate_manifest_for_guppy_test(test_env_namespace: str):
    """
    Runs jenkins job to point guppy to pre-defined Canine ETL'ed data
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-mutate-manifest-for-guppy-test",
        )
        params = {
            "NAMESPACE": test_env_namespace,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return True
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        pass


def clean_up_indices(test_env_namespace: str):
    """
    Runs jenkins job to clean up indices before running the ETL tests
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-clean-up-indices",
        )
        params = {"NAMESPACE": test_env_namespace}
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num, max_duration=300)
            if status == "Completed":
                return True
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        pass


def check_indices_after_etl(test_env_namespace: str):
    """
    Runs jenkins job to clean up indices before running the ETL tests
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-check_indices_after_etl",
        )
        params = {"NAMESPACE": test_env_namespace}
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num, max_duration=300)
            if status == "Completed":
                return True
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        pass


def create_access_token(test_env_namespace, service, expired, username):
    """
    Roll a give service pod
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-create-access-token",
        )
        if expired:
            expiration = 1
        else:
            expiration = 300  # 5 min
        params = {
            "SERVICE": service,
            "EXPIRATION": expiration,
            "USERNAME": username,
            "NAMESPACE": test_env_namespace,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num, max_duration=300)
            if status == "Completed":
                if expired:
                    time.sleep(expiration)
                return job.get_artifact_content(build_num, "access_token.txt")
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        cmd = f"kubectl get pods -l app={service} | awk '{{print $1}}' | tail -n 1"
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True
        )
        if result.returncode == 0:
            fence_pod_name = result.stdout.strip()
        else:
            raise Exception("Unable to retrieve fence-deployment pod")
        cmd = f"kubectl exec -it {fence_pod_name} -- fence-create token-create --scopes openid,user,fence,data,credentials,google_service_account,google_credentials --type access_token --exp {expired} --username {username}"
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            raise Exception("Unable to get expired access_token")


# TODO remove this if unused... in a while
def kube_setup_service(test_env_namespace, servicename):
    """
    Runs jenkins job to kube setup service
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-kube-setup-service",
        )
        params = {
            "SERVICENAME": servicename,
            "NAMESPACE": test_env_namespace,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return True
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        pass


def create_link_google_test_buckets(test_env_namespace: str):
    """
    Runs jenkins job to execute command for creating and linking Google test buckets
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-create-link-google-test-buckets",
        )
        params = {
            "NAMESPACE": test_env_namespace,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return True
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        pass


def fence_enable_register_users_redirect(test_env_namespace: str):
    """
    Runs jenkins job to setup register user redirect on login
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-fence-enable-user-register-redirect",
        )
        params = {
            "NAMESPACE": test_env_namespace,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return True
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        pass


def fence_disable_register_users_redirect(test_env_namespace: str):
    """
    Runs jenkins job to disable register user redirect on login
    """
    # Admin VM Deployments
    if os.getenv("GEN3_INSTANCE_TYPE") == "ADMINVM_REMOTE":
        job = JenkinsJob(
            os.getenv("JENKINS_URL"),
            os.getenv("JENKINS_USERNAME"),
            os.getenv("JENKINS_PASSWORD"),
            "ci-only-fence-disable-user-register-redirect",
        )
        params = {
            "NAMESPACE": test_env_namespace,
        }
        build_num = job.build_job(params)
        if build_num:
            status = job.wait_for_build_completion(build_num)
            if status == "Completed":
                return True
            else:
                job.terminate_build(build_num)
                raise Exception("Build timed out. Consider increasing max_duration")
        else:
            raise Exception("Build number not found")
    # Local Helm Deployments
    elif os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL":
        pass
