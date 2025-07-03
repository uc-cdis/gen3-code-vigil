import os
import subprocess
import time

from utils import logger

RELEASE_NAME = os.getenv("NAMESPACE")
NAMESPACE = os.getenv("NAMESPACE")
INSTANCE_TYPE = os.getenv("GEN3_INSTANCE_TYPE")


def delete_helm_release():
    """Delete the helm release from the namespace"""
    cmd = [
        "helm",
        "delete",
        RELEASE_NAME,
        "-n",
        NAMESPACE,
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        return result.stdout.strip()
    else:
        logger.info(result.stderr)
        raise Exception(f"Unable to delete environment {NAMESPACE}")


def delete_helm_pvcs():
    """Delete the pvs from the namespace"""
    for label in ["app.kubernetes.io/name=postgresql", "app=gen3-elasticsearch-master"]:
        cmd = (
            "kubectl get pvc -n "
            + NAMESPACE
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
                    NAMESPACE,
                    "--wait=false",
                ]
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                if result.returncode != 0:
                    raise Exception(f"Unable to delete pvc for {label}")
                pvc_status = get_pvc_status(pvc)
                if not pvc_status:
                    force_remove_pvc(pvc)
                force_remove_pvc(pvc)
        else:
            logger.info(result.stderr)


def get_pvc_status(pvc):
    for i in range(10):
        cmd = [
            "kubectl",
            "get",
            "pvc",
            pvc,
            "-n",
            NAMESPACE,
        ]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.stdout.strip() == "":
            return True
        time.sleep(30)
    return False


def force_remove_pvc(pvc):
    """Force removes the pvs from the namespace"""
    cmd = [
        "kubectl",
        "patch",
        "pvc",
        pvc,
        "-n",
        NAMESPACE,
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
        raise Exception(f"Unable to force remove pvc {pvc} from {NAMESPACE}")


def delete_k8s_namespace():
    """Delete the k8s namespace from the from the kubernetes cluster"""
    cmd = ["kubectl", "delete", "ns", NAMESPACE]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        return result.stdout.strip()
    else:
        logger.info(result.stderr)
        raise Exception(f"Unable to delete namespace {NAMESPACE}")


def delete_helm_jupyter_pod_namespace():
    """Delete the jupyter pods namespace from the kubernetes cluster"""
    cmd = ["kubectl", "delete", "ns", f"jupyter-pods-{NAMESPACE}"]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if result.returncode == 0:
        logger.info(f"Deleted namespace jupyter-pods-{NAMESPACE} successfully")
    else:
        logger.info(result.stderr)


def delete_sqs_queues():
    """Delete the aws sqs queues for audit-service-sqs and data-upload-bucket"""
    audit_queue_url = f"https://sqs.us-east-1.amazonaws.com/707767160287/ci-audit-service-sqs-{NAMESPACE}"
    upload_queue_url = f"https://sqs.us-east-1.amazonaws.com/707767160287/ci-data-upload-bucket-{NAMESPACE}"
    for queue in [audit_queue_url, upload_queue_url]:
        cmd = ["aws", "sqs", "get-queue-attributes", "--queue-url", queue]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0 and result.stdout.strip() != "":
            subscription_arn_cmd = [
                "aws",
                "sns",
                "list-subscriptions-by-topic",
                "--topic-arn",
                "arn:aws:sns:us-east-1:707767160287:ci-data-upload-bucket",
                "--query",
                f"Subscriptions[?Endpoint=='https://sqs.us-east-1.amazonaws.com/707767160287/ci-data-upload-bucket-${NAMESPACE}'].SubscriptionArn",
                "--output",
                "text",
            ]
            subscription_arn_result = subprocess.run(
                subscription_arn_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if (
                subscription_arn_result.returncode == 0
                and subscription_arn_result.stdout.strip() != "PendingConfirmation"
            ):
                unsubscribe_arn_cmd = [
                    "aws",
                    "sns",
                    "unsubscribe",
                    "--subscription-arn",
                    subscription_arn_result.stdout.strip(),
                ]
                unsubscribe_arn_result = subprocess.run(
                    unsubscribe_arn_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if unsubscribe_arn_result.returncode == 0:
                    logger.info(
                        f"Unsubscribed: {subscription_arn_result.stdout.strip()}"
                    )
                else:
                    logger.info(
                        f"Unable to unsubscribe {subscription_arn_result.stdout.strip()}"
                    )
                    logger.info(subscription_arn_result.stderr)
            else:
                logger.info("Unable to list subscriptions")
                logger.info(subscription_arn_cmd.stderr)

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


def teardown_helm_environment():
    # Delete the helm environment
    delete_helm_release()
    delete_helm_pvcs()
    delete_k8s_namespace()
    delete_helm_jupyter_pod_namespace()
    delete_sqs_queues()


if __name__ == "__main__":
    with open("output/report.md", "r", encoding="utf-8") as file:
        content = file.read().lower()
    if (
        "failed" not in content
        and "error" not in content
        and INSTANCE_TYPE == "HELM_LOCAL"
    ):
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
