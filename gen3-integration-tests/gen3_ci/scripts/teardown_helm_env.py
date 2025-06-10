import os
import subprocess
import time

from utils import logger


def delete_helm_environment(namespace):
    cmd = [
        "helm",
        "delete",
        namespace,
        "-n",
        namespace,
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        return result.stdout.strip()
    else:
        logger.info(result.stderr)
        raise Exception(f"Unable to delete environment {namespace}")


def delete_helm_pvcs(namespace):
    for label in ["app.kubernetes.io/name=postgresql", "app=gen3-elasticsearch-master"]:
        cmd = (
            "kubectl get pvc -n "
            + namespace
            + " -l "
            + label
            + " -o name | head -n 1 | cut -d'/' -f2"
        )
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, shell=True, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            if result.stdout.strip() != "":
                pvc = result.stdout.strip()
                cmd = [
                    "kubectl",
                    "delete",
                    "pvc",
                    pvc,
                    "-n",
                    namespace,
                    "--wait=false",
                ]
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                if result.returncode != 0:
                    raise Exception(f"Unable to delete pvc for {label}")
                pvc_status = get_pvc_status(namespace, pvc)
                if not pvc_status:
                    force_remove_pvc(namespace, pvc)
        else:
            logger.info(result.stderr)
            raise Exception(f"Unable to delete pvc for {label}")


def get_pvc_status(namespace, pvc):
    for i in range(15):
        cmd = [
            "kubectl",
            "get",
            "pvc",
            pvc,
            "-n",
            namespace,
        ]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.stdout.strip() == "":
            return True
        time.sleep(5)
    return False


def force_remove_pvc(namespace, pvc):
    cmd = [
        "kubectl",
        "patch",
        "pvc",
        pvc,
        "-n",
        namespace,
        "-p",
        '\'{"metadata":{"finalizers":null}}\'',
        "--type=merge",
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        return result.stdout.strip()
    else:
        logger.info(result.stderr)
        raise Exception(f"Unable to force remove pvc {pvc} from {namespace}")


def delete_helm_namespace(namespace):
    cmd = ["kubectl", "delete", "ns", namespace]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        return result.stdout.strip()
    else:
        logger.info(result.stderr)
        raise Exception(f"Unable to delete namespace {namespace}")


def delete_helm_jupyter_pod_namespace(namespace):
    cmd = ["kubectl", "delete", "ns", f"jupyter-pods-{namespace}"]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        logger.info(f"Deleted namespace jupyter-pods-{namespace} successfully")
    else:
        logger.info(result.stderr)


def delete_sqs_queues(namespace):
    audit_queue_url = f"https://sqs.us-east-1.amazonaws.com/707767160287/ci-audit-service-sqs-{namespace}"
    upload_queue_url = f"https://sqs.us-east-1.amazonaws.com/707767160287/ci-data-upload-bucket-{namespace}"
    for queue in [audit_queue_url, upload_queue_url]:
        cmd = ["aws", "sqs", "get-queue-attributes", "--queue-url", queue]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0 and result.stdout.strip() != "":
            queue_deletion_cmd = ["aws", "sqs", "delete-queue", "--queue-url", queue]
            queue_deletion_result = subprocess.run(
                queue_deletion_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if queue_deletion_result.returncode == 0:
                logger.info(f"Deleted sqs queue {queue}")
            else:
                logger.info(f"Unable to delete sqs queue {queue}")
                logger.info(queue_deletion_result.stderr)
        else:
            logger.info(f"Queue not found. Skipping sqs deletion of {queue}")


def teardown_helm_environment(namespace):
    # Delete the helm environment
    delete_helm_environment(namespace)
    delete_helm_pvcs(namespace)
    delete_helm_namespace(namespace)
    delete_helm_jupyter_pod_namespace(namespace)
    delete_sqs_queues(namespace)


if __name__ == "__main__":
    namespace = os.getenv("NAMESPACE")
    with open("output/report.md", "r", encoding="utf-8") as file:
        content = file.read().lower()
    if (
        "failed" not in content
        and "error" not in content
        and os.getenv("GEN3_INSTANCE_TYPE") == "HELM_LOCAL"
    ):
        logger.info(f"Tearing down environment: {namespace}")
        teardown_helm_environment(namespace)
