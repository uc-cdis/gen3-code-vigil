#!/bin/bash

# This script helps setup the gen3-helm env for running intergration tests.
# It contains 3 blocks, test-env-setup, service-env-setup and manifest-env-setup.

# Inputs:
# namespace - namespace aginst which env is setup
# setup_type - type of setup being performed
# helm_branch - gen3 helm branch to bring up the env

namespace="$1"
helm_branch="$2"
manifest_dir="$3"
manifest_values_yaml="${manifest_dir}/values.yaml"
master_values_yaml="master_values.yaml"

touch $master_values_yaml

for file in "$manifest_dir"/*.yaml; do
  if [[ -f "$file" ]]; then
    echo "" >> "$master_values_yaml"
    cat "$file" >> "$master_values_yaml"
  fi
done

# Move the combined file to values.yaml
mv "$master_values_yaml" "$manifest_values_yaml"

####################################################################################
# Update images for each service from $new_manifest_values_file_path
####################################################################################
echo "###################################################################################"
if [[ -n $RELEASE_VERSION ]]; then
  INTEGRATION_BRANCH="integration${RELEASE_VERSION/./}"
  echo "INTEGRATION BRANCH value : ${INTEGRATION_BRANCH}"
  keys_ci=$(yq eval 'keys' $manifest_values_yaml -o=json | jq -r '.[]')
  for key in $keys_ci; do
  if [[ "$key" != "global" && "$key" != "postgresql" && "$key" != "elasticsearch" ]]; then
    service_enabled_value=$(yq eval ".${key}.enabled" $manifest_values_yaml)
    image_tag_value=$(yq eval ".${key}.image.tag" $manifest_values_yaml 2>/dev/null)
    if ! grep -q $key $THOR_REPO_LIST_PATH; then
        echo "Skipping image update for ${key} as service is not present in Thor repo_list.txt"
    elif [ "$(echo -n $service_enabled_value)" = "false" ]; then
        echo "Skipping image update for ${key} as service enabled is set to false"
    elif [ ! -z "$image_tag_value" ]; then
        echo "Updating ${key} service from ${image_tag_value} to ${INTEGRATION_BRANCH}"
        yq eval ".${key}.image.tag = \"$INTEGRATION_BRANCH\"" -i $manifest_values_yaml
    fi
  else
    echo "Skipping image update for ${key}"
  fi
  done
fi

# Generate Google Prefix by using commit sha so it is unqiue for each env.
ENV_PREFIX=$NAMESPACE
echo "Last 6 characters of COMMIT_SHA: $ENV_PREFIX"
yq eval ".fence.FENCE_CONFIG_PUBLIC.GOOGLE_GROUP_PREFIX = \"$ENV_PREFIX\"" -i $manifest_values_yaml
yq eval ".fence.FENCE_CONFIG_PUBLIC.GOOGLE_SERVICE_ACCOUNT_PREFIX = \"$ENV_PREFIX\"" -i $manifest_values_yaml

# Update indexd values to set a dynamic prefix for each env and set a pw for ssj/gateway in the indexd database.
yq eval ".indexd.defaultPrefix = \"$ENV_PREFIX/\"" -i $manifest_values_yaml
yq eval ".indexd.secrets.userdb.fence = \"$EKS_CLUSTER_NAME\"" -i $manifest_values_yaml
yq eval ".indexd.secrets.userdb.sheepdog = \"$EKS_CLUSTER_NAME\"" -i $manifest_values_yaml
yq eval ".indexd.secrets.userdb.ssj = \"$EKS_CLUSTER_NAME\"" -i $manifest_values_yaml
yq eval ".indexd.secrets.userdb.gateway = \"$EKS_CLUSTER_NAME\"" -i $manifest_values_yaml

# Create sqs queues and save to var.
AUDIT_QUEUE_NAME="ci-audit-service-sqs-${namespace}"
AUDIT_QUEUE_URL=$(aws sqs create-queue --queue-name "$AUDIT_QUEUE_NAME" --query 'QueueUrl' --output text)
UPLOAD_QUEUE_NAME="ci-data-upload-bucket-${namespace}"
UPLOAD_QUEUE_URL=$(aws sqs create-queue --queue-name "$UPLOAD_QUEUE_NAME" --query 'QueueUrl' --output text)
UPLOAD_QUEUE_ARN=$(aws sqs get-queue-attributes --queue-url "$UPLOAD_QUEUE_URL" --attribute-name QueueArn --query 'Attributes.QueueArn' --output text)
UPLOAD_SNS_NAME="ci-data-upload-bucket"
UPLOAD_SNS_ARN="arn:aws:sns:us-east-1:707767160287:ci-data-upload-bucket"

if [ -z "$AUDIT_QUEUE_URL" ]; then
  echo "Initial Audit SQS queue creation failed, retrying in 60 seconds..."
  sleep 60
  AUDIT_QUEUE_URL=$(aws sqs create-queue --queue-name "$AUDIT_QUEUE_NAME" --query 'QueueUrl' --output text)
  if [ -z "$AUDIT_QUEUE_URL" ]; then
    echo "SQS Audit queue creation failed after retry."
    exit 1
  fi
fi

if [ -z "$UPLOAD_QUEUE_URL" ]; then
  echo "Initial Upload SQS queue creation failed, retrying in 60 seconds..."
  sleep 60
  UPLOAD_QUEUE_URL=$(aws sqs create-queue --queue-name "$UPLOAD_QUEUE_NAME" --query 'QueueUrl' --output text)
  if [ -z "$UPLOAD_QUEUE_URL" ]; then
    echo "SQS Upload queue creation failed after retry."
    exit 1
  fi
fi


# Update values.yaml to use sqs queues.
yq eval ".audit.server.sqs.url = \"$AUDIT_QUEUE_URL\"" -i $manifest_values_yaml
yq eval ".ssjdispatcher.ssjcreds.sqsUrl = \"$UPLOAD_QUEUE_URL\"" -i $manifest_values_yaml
yq eval ".fence.FENCE_CONFIG_PUBLIC.PUSH_AUDIT_LOGS_CONFIG.aws_sqs_config.sqs_url = \"$AUDIT_QUEUE_URL\"" -i $manifest_values_yaml

# Subscribing the SQS queue to the SNS topic.
aws sns subscribe \
  --topic-arn "$UPLOAD_SNS_ARN" \
  --protocol sqs \
  --notification-endpoint "$UPLOAD_QUEUE_ARN"

# Set SQS policy on SQS queue.
cat <<EOF > raw-policy.json
{
  "Version": "2012-10-17",
  "Id": "sqspolicy",
  "Statement": [
    {
      "Sid": "100",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "sqs:SendMessage",
      "Resource": "$UPLOAD_QUEUE_ARN",
      "Condition": {
        "ArnEquals": {
          "aws:SourceArn": "$UPLOAD_SNS_ARN"
        }
      }
    }
  ]
}
EOF

# Step 2: Escape the policy JSON into a single string and embed it in the final file and save as final attributes JSON
escaped_policy=$(jq -c . raw-policy.json | jq -R '{ Policy: . }')
echo "$escaped_policy" > policy.json

if ! aws sqs set-queue-attributes \
  --queue-url "$UPLOAD_QUEUE_URL" \
  --attributes file://policy.json ; then
  echo "❌ Failed to set SQS queue attributes" >&2
  exit 1
fi

# Update ssjdispatcher configuration.
yq eval ".ssjdispatcher.ssjcreds.jobPattern = \"s3://gen3-helm-data-upload-bucket/${ENV_PREFIX}/*\"" -i "$manifest_values_yaml"
yq eval ".ssjdispatcher.ssjcreds.jobPassword = \"$EKS_CLUSTER_NAME\"" -i $manifest_values_yaml
yq eval ".ssjdispatcher.ssjcreds.metadataservicePassword = \"$EKS_CLUSTER_NAME\"" -i $manifest_values_yaml

# Add in hostname/namespace for revproxy, ssjdispatcher, hatchery, fence, and manifestservice configuration.
yq eval ".global.environment = \"$namespace\"" -i $manifest_values_yaml
yq eval ".revproxy.ingress.hosts[0].host = \"$HOSTNAME\"" -i $manifest_values_yaml
yq eval ".manifestservice.manifestserviceG3auto.hostname = \"$HOSTNAME\"" -i $manifest_values_yaml
yq eval ".fence.FENCE_CONFIG_PUBLIC.BASE_URL = \"https://${HOSTNAME}/user\"" -i $manifest_values_yaml
yq eval ".ssjdispatcher.gen3Namespace = \"${namespace}\"" -i $manifest_values_yaml
yq eval ".gen3-workflow.externalSecrets.funnelOidcClient = \"${namespace}-funnel-oidc-client\"" -i $manifest_values_yaml
yq eval ".gen3-workflow.funnel.Kubernetes.JobsNamespace = \"gen3-${namespace}-workflow-pods\"" -i $manifest_values_yaml
yq eval ".gen3-workflow.funnel.Plugins.Params.S3Url = \"gen3-workflow-service.${namespace}.svc.cluster.local\"" -i $manifest_values_yaml
yq eval ".gen3-workflow.funnel.Plugins.Params.OidcTokenUrl = \"https://${HOSTNAME}/user\"" -i $manifest_values_yaml
sed -i "s|FRAME_ANCESTORS: .*|FRAME_ANCESTORS: https://${HOSTNAME}|" $manifest_values_yaml

# Remove aws-es-proxy block
yq -i 'del(.aws-es-proxy)' $manifest_values_yaml

# Check if sheepdog's fenceUrl key is present and update it
sheepdog_fence_url=$(yq eval ".sheepdog.fenceUrl // \"key not found\"" "$manifest_values_yaml")
if [ "$sheepdog_fence_url" != "key not found" ]; then
    echo "Key sheepdog.fenceUrl found in \"$manifest_values_yaml\""
    yq eval ".sheepdog.fenceUrl = \"https://$HOSTNAME/user\"" -i "$manifest_values_yaml"
fi

# Check if global manifestGlobalExtraValues fenceUrl key is present and update it.
manifest_global_extra_values_fence_url=$(yq eval ".global.fenceURL // \"key not found\"" "$manifest_values_yaml")
if [ "$manifest_global_extra_values_fence_url" != "key not found" ]; then
    echo "Key global.fenceURL found in \"$manifest_values_yaml\""
    yq eval ".global.fenceURL = \"https://$HOSTNAME/user\"" -i "$manifest_values_yaml"
fi

# Update replicaCount for certain services
yq eval ".fence.replicaCount = \"6\"" -i "$manifest_values_yaml"
yq eval ".indexd.replicaCount = \"3\"" -i "$manifest_values_yaml"

# delete the ssjdispatcher deployment so a new one will get created and use the new configuration file.
kubectl delete deployment -l app=ssjdispatcher -n ${namespace}

# Set env variable for ETL enabled or not
ETL_ENABLED=$(yq '.etl.enabled // "false"' "$manifest_values_yaml")
echo "ETL_ENABLED=$ETL_ENABLED" >> "$GITHUB_ENV"

# Ensure funnel-oidc-client for this namespace does not exist in secrets manager before installing the helm chart
echo "Deleting $namespace-funnel-oidc-client from aws secrets manager, if it exists"
aws secretsmanager delete-secret --secret-id $namespace-funnel-oidc-client --force-delete-without-recovery 2>&1

echo $HOSTNAME
install_helm_chart() {
  #For custom helm branch
  if [ "$helm_branch" != "master" ]; then
    git clone --branch "$helm_branch" https://github.com/uc-cdis/gen3-helm.git
    echo "dependency update"
    helm dependency update gen3-helm/helm/gen3
    echo "grep"
    cat $manifest_values_yaml | grep -i "elasticsearch:"
    echo "installing helm chart"
    if helm upgrade --install ${namespace} gen3-helm/helm/gen3 --set global.hostname="${HOSTNAME}" -f $manifest_values_yaml -n "${NAMESPACE}"; then
      echo "Helm chart installed!"
    else
      return 1
    fi
  else
    helm repo add gen3 https://helm.gen3.org
    helm repo update
    if helm upgrade --install ${namespace} gen3/gen3 --set global.hostname="${HOSTNAME}" -f $manifest_values_yaml -n "${NAMESPACE}"; then
      echo "Helm chart installed!"
    else
      return 1
    fi
  fi
  return 0
}

ci_es_indices_setup() {
  echo "Setting up ES port-forward..."
  label="app=gen3-elasticsearch-master"
  max_retries=3
  delay=30

  for attempt in $(seq 0 $max_retries); do
    echo "Attempt $((attempt + 1))..."
    if kubectl get pod -l "$label" -n ${namespace}| grep -q 'gen3-elasticsearch-master'; then
      if kubectl wait --for=condition=ready pod -l "$label" --timeout=5m -n ${namespace}; then
        echo "Pod is ready!"
        break
      fi
    else
      echo "Elasticsearch Pod not found."
    fi

    if [ "$attempt" -lt "$max_retries" ]; then
      echo "Retrying in $delay seconds..."
      sleep "$delay"
    else
      echo "Failed after $((max_retries + 1)) attempts."
      exit 1
    fi
  done

  echo "Running ci_setup.sh with timeout..."
  chmod 755 test_data/test_setup/ci_es_setup/ci_setup.sh
  touch output.txt
  bash test_data/test_setup/ci_es_setup/ci_setup.sh ${namespace} &> output.txt
  # cat output.txt
  kubectl delete pods -l app=guppy -n ${namespace}

  echo "Killing port-forward process..."
}

wait_for_pods_ready() {
  export timeout=900
  export interval=20

  end=$((SECONDS + timeout))
  while [ $SECONDS -lt $end ]; do
    # Get JSON for not-ready, non-terminating pods
    not_ready_json=$(kubectl get pods -l app!=gen3job -n "${NAMESPACE}" -o json | \
      jq '[.items[]
        | select(
            (.metadata.deletionTimestamp == null) and
            ((.status.phase != "Running") or
            (.status.containerStatuses[]?.ready != true))
        )
      ]')

    not_ready_count=$(echo "$not_ready_json" | jq 'length')

    if [ "$not_ready_count" -eq 0 ]; then
      echo "✅ All pods containers are Ready"
      return 0
    fi

    echo "⏳ Waiting... ($not_ready_count pods have containers not ready)"
    sleep $interval
  done

  echo "❌ Timeout: Pods' containers not ready"
  echo "$not_ready_json" | jq -r '.[] |
    .metadata.name as $pod_name |
    .status.containerStatuses[]?
    | select(.ready != true)
    | "🔴 Pod: \($pod_name), Container: \(.name) is NOT ready"'

  kubectl get pods -n "${NAMESPACE}"
  return 1
}

# 🚀 Run the helm install and then wait for pods if successful
if install_helm_chart; then
  ci_es_indices_setup
  kubectl rollout restart guppy-deployment
  wait_for_pods_ready
  if [[ $? -ne 0 ]]; then
    echo "❌ wait_for_pods_ready failed"
    exit 1
  fi
else
  echo "❌ Helm chart installation failed"
  exit 1
fi

kubectl delete job usersync-manual -n ${namespace}
kubectl create job --from=cronjob/usersync usersync-manual -n ${namespace}
kubectl wait --for=condition=complete job/usersync-manual --namespace=${namespace} --timeout=5m

echo "YAY!!! Env is up..."
