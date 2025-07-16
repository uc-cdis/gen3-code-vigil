#!/bin/bash

# This script helps setup the gen3-helm env for running intergration tests.
# It contains 3 blocks, test-env-setup, service-env-setup and manifest-env-setup.

# Inputs:
# namespace - namespace aginst which env is setup
# setup_type - type of setup being performed
# helm_branch - gen3 helm branch to bring up the env

namespace="$1"
setup_type="$2"
helm_branch="$3"
ci_default_manifest_dir="$4"
ci_default_manifest_values_yaml="${ci_default_manifest_dir}/values.yaml"
master_values_yaml="master_values.yaml"

touch $master_values_yaml

for file in "$ci_default_manifest_dir"/*.yaml; do
  if [[ -f "$file" ]]; then
    echo "" >> "$master_values_yaml"
    cat "$file" >> "$master_values_yaml"
  fi
done

# Move the combined file to values.yaml
mv "$master_values_yaml" "$ci_default_manifest_values_yaml"


if [ "$setup_type" == "test-env-setup" ] ; then
    # If PR is under test repository, then do nothing
    echo "Setting Up Test PR Env..."
elif [ "$setup_type" == "service-env-setup" ]; then
    # If PR is under a service repository, then update the image for the given service
    echo "Setting Up Service PR Env..."
    # Inputs:
    # service_name - name of service against which PR is run
    # image_name - name of the quay image for the service PR
    service_name="$5"
    image_name="$6"
    service_values_block=$(yq eval ".${service_name} // \"key not found\"" "$ci_default_manifest_values_yaml")
    if [ "$service_values_block" != "key not found" ]; then
        echo "Key '$service_name' found in \"$ci_default_manifest_values_yaml.\""
        if [[ "$service" == "etl" ]]; then
          yq eval ".${service_name}.image.tube.tag = \"${image_name}\"" -i "$ci_default_manifest_values_yaml"
        else
          yq eval ".${service_name}.image.tag = \"${image_name}\"" -i "$ci_default_manifest_values_yaml"
        fi
    elif [ "$service_yaml_block" != "key not found" ]; then
        echo "Key '$service_name' not found.\""
        exit 1
    fi
elif [ "$setup_type" == "manifest-env-setup" ]; then
    # If PR is under a manifest repository, then update the yaml files as needed
    echo "Setting Up Manifest PR Env..."
    # Inputs:
    # ci_default_manifest - name of the folder containing default ci env configuration
    # target_manifest_path - name of the folder containing manifest env configuration

    target_manifest_path="${5}"
    echo "CI Default Env Configuration Folder Path: ${ci_default_manifest_dir}"
    echo "New Env Configuration Folder Path: ${target_manifest_path}"

    # Check if multiple yaml files are present and convert them into values.yaml
    new_manifest_values_file_path=$ci_default_manifest_dir/manifest_values.yaml
    for file in "$target_manifest_path"/*.yaml; do
      if [[ -f "$file" ]]; then
        echo >> "$new_manifest_values_file_path"
        cat "$file" >> "$new_manifest_values_file_path"
      fi
    done


    ####################################################################################
    # Update all AWS images to QUAY
    ####################################################################################
    # sed -i 's/[a-zA-Z0-9.-]*\.dkr\.ecr\.us-east-1\.amazonaws\.com\/gen3/quay.io\/cdis/g' $new_manifest_values_file_path

    ####################################################################################
    # Update ETL Block
    ####################################################################################
    etl_block=$(yq eval ".etl // \"key not found\"" $new_manifest_values_file_path)
    if [ "$etl_block" != "key not found" ]; then
        echo "Updating ETL Block"
        yq eval ". |= . + {\"etl\": $(yq eval .etl $new_manifest_values_file_path -o=json)}" -i $ci_default_manifest_values_yaml
        yq eval ".etl.esEndpoint = \"gen3-elasticsearch-master\"" -i $ci_default_manifest_values_yaml
    fi

    ####################################################################################
    # Update HATCHERY  Block
    ####################################################################################
    hatchery_block=$(yq eval ".hatchery // \"key not found\"" $new_manifest_values_file_path)
    if [ "$hatchery_block" != "key not found" ]; then
        echo "Updating HATCHERY Block"
        yq eval ". |= . + {\"hatchery\": $(yq eval .hatchery $new_manifest_values_file_path -o=json)}" -i $ci_default_manifest_values_yaml
    fi

    ####################################################################################
    # Update PORTAL Block
    ####################################################################################
    portal_block=$(yq eval ".portal // \"key not found\"" $new_manifest_values_file_path)
    if [ "$portal_block" != "key not found" ]; then
        echo "Updating PORTAL Block"
        #yq -i '.portal.resources = load(env(ci_default_manifest) + "/values.yaml").portal.resources' $new_manifest_values_file_path
        yq eval ". |= . + {\"portal\": $(yq eval .portal $new_manifest_values_file_path -o=json)}" -i $ci_default_manifest_values_yaml
        yq -i 'del(.portal.replicaCount)' $ci_default_manifest_values_yaml
        sed -i '/requiredCerts/d' "$ci_default_manifest_values_yaml"
    fi

    ####################################################################################
    # Make sure the blocks of values.yaml in ci default are in reflection of the blocks
    # of values.yaml in new_manifest_values_file_path.
    ####################################################################################
    # Get all the top-level keys from both files
    keys_ci=$(yq eval 'keys' $ci_default_manifest_values_yaml -o=json | jq -r '.[]')
    keys_manifest=$(yq eval 'keys' $new_manifest_values_file_path -o=json | jq -r '.[]')

    # Remove blocks from $ci_default_manifest_values_yaml that are not present in new_manifest_values_file_path
    echo "###################################################################################"
    for key in $keys_ci; do
    if ! echo "$keys_manifest" | grep -q "^$key$"; then
        if [[ "$key" != "postgresql" && "$key" != "global" && "$key" != "external-secrets" ]]; then
            echo "Removing ${key} section in default ci manifest as its not present in target manifest"
            yq eval "del(.$key)" -i $ci_default_manifest_values_yaml
        fi
    fi
    done

    # Add blocks from new_manifest_values_file_path that are not present in $ci_default_manifest_values_yaml
    echo "###################################################################################"
    for key in $keys_manifest; do
    if ! echo "$keys_ci" | grep -q "^$key$"; then
      if [[ "$key" != "mutatingWebhook" && "$key" != "neuvector" && "$key" != "dashboard" ]]; then
        echo "Adding ${key} section in default ci manifest as its present in target manifest"
        yq eval ". |= . + {\"$key\": $(yq eval .$key $new_manifest_values_file_path -o=json)}" -i $ci_default_manifest_values_yaml
      fi
    fi
    done

    ####################################################################################
    # Update images for each service from $new_manifest_values_file_path
    ####################################################################################
    echo "###################################################################################"
    for key in $keys_manifest; do
    if [ "$key" != "global" ]; then
      service_enabled_value=$(yq eval ".${key}.enabled" $new_manifest_values_file_path)
      image_tag_value=$(yq eval ".${key}.image.tag" $new_manifest_values_file_path 2>/dev/null)
      # Check if the service_enabled_value is false
      if [ "$(echo -n $service_enabled_value)" = "false" ]; then
          echo "Disabling ${key} service as enabled is set to ${service_enabled_value} in new manifest values"
          yq eval ".${key}.enabled = false" -i "$ci_default_manifest_values_yaml"
      elif [ "$image_tag_value" = "null" ]; then
          echo "Using CI default image value for ${key}"
      else
        echo "Updating ${key} service with ${image_tag_value}"
        if [ ! -z "$image_tag_value" ]; then
            yq eval ".${key}.image.tag = \"$image_tag_value\"" -i $ci_default_manifest_values_yaml
        fi
      fi
    else
      echo "Skipping image update for global section"
    fi
    done

    ############################################################################################################################
    # Perform operations for global and other sections under values.yaml
    ############################################################################################################################
    keys=("global.dictionaryUrl"
     "global.portalApp"
     "global.netpolicy"
     "global.frontendRoot"
     #"google.enabled"
     "ssjdispatcher.indexing"
     # "metadata.useAggMds"
     # "metadata.aggMdsNamespace"
     # "metadata.aggMdsDefaultDataDictField"
     #"sower.sowerConfig"
     )
    echo "###################################################################################"
    for key in "${keys[@]}"; do
        ci_value=$(yq eval ".$key // \"key not found\"" $ci_default_manifest_values_yaml)
        manifest_value=$(yq eval ".$key // \"key not found\"" $new_manifest_values_file_path)
        if [ "$manifest_value" = "key not found" ]; then
            echo "The key '$key' is not present in target manifest."
        else
            echo "CI default value of the key '$key' is: $ci_value"
            echo "Manifest value of the key '$key' is: $manifest_value"
            yq eval ".${key} = \"${manifest_value}\"" -i "$ci_default_manifest_values_yaml"
        fi
    done

    ############################################################################################################################
    # Set jupyterNamespace to empty for ambassador and hatchery if found
    ############################################################################################################################
    keys=("ambassador.jupyterNamespace"
    "hatchery.jupyterNamespace")
    echo "###################################################################################"
    for key in "${keys[@]}"; do
        ci_value=$(yq eval ".$key // \"key not found\"" $ci_default_manifest_values_yaml)
        if [ "$ci_value" = "key not found" ]; then
            echo "The key '$key' is not present in target manifest."
        else
            echo "CI default value of the key '$key' is: $ci_value"
            yq eval ".${key} = \"\"" -i "$ci_default_manifest_values_yaml"
        fi
    done

    # Update mds_url and common_url under metadata if present
    json_content=$(yq eval ".metadata.aggMdsConfig // \"key not found\"" "$ci_default_manifest_values_yaml")
    if [ -n "$json_content" ] && [ "$json_content" != "key not found" ]; then
        # Extract and update mds_url
        current_mds_url=$(echo "$json_content" | jq -r ".adapter_commons.gen3.mds_url // \"key not found\"")
        if [ "$current_mds_url" != "key not found" ]; then
            modified_json=$(echo "$json_content" | jq ".adapter_commons.gen3.mds_url = \"https://${namespace}.planx-pla.net/\"")
            yq eval --inplace ".metadata.aggMdsConfig = ${modified_json}" "$ci_default_manifest_values_yaml"
        fi

        # Extract and update commons_url
        current_commons_url=$(echo "$json_content" | jq -r ".adapter_commons.gen3.commons_url // \"key not found\"")
        if [ "$current_commons_url" != "key not found" ]; then
            modified_json=$(echo "$json_content" | jq ".adapter_commons.gen3.commons_url = \"${namespace}.planx-pla.net/\"")
            yq eval --inplace ".metadata.aggMdsConfig = ${modified_json}" "$ci_default_manifest_values_yaml"
        fi
    fi

    # TODO : Update the SA names for sower jobs in SowerConfig section
    current_sower_service_account=$(yq eval ".sower.serviceAccount.name // \"key not found\"" "$ci_default_manifest_values_yaml")
    if [ "$current_sower_service_account" != "key not found" ]; then
        echo "Key sower.serviceAccount.name found in \"$ci_default_manifest_values_yaml.\""
        yq eval ".sower.serviceAccount.name = \"sower-service-account\"" -i "$ci_default_manifest_values_yaml"
    fi
fi

# Generate Google Prefix by using commit sha so it is unqiue for each env.
commit_sha="${COMMIT_SHA}"
ENV_PREFIX="${commit_sha: -6}"
echo "Last 6 characters of COMMIT_SHA: $ENV_PREFIX"
yq eval ".fence.FENCE_CONFIG_PUBLIC.GOOGLE_GROUP_PREFIX = \"ci$ENV_PREFIX\"" -i $ci_default_manifest_values_yaml
yq eval ".fence.FENCE_CONFIG_PUBLIC.GOOGLE_SERVICE_ACCOUNT_PREFIX = \"ci$ENV_PREFIX\"" -i $ci_default_manifest_values_yaml

# Update indexd values to set a dynamic prefix for each env and set a pw for ssj/gateway in the indexd database.
yq eval ".indexd.defaultPrefix = \"ci$ENV_PREFIX/\"" -i $ci_default_manifest_values_yaml
yq eval ".indexd.secrets.userdb.fence = \"$EKS_CLUSTER_NAME\"" -i $ci_default_manifest_values_yaml
yq eval ".indexd.secrets.userdb.sheepdog = \"$EKS_CLUSTER_NAME\"" -i $ci_default_manifest_values_yaml
yq eval ".indexd.secrets.userdb.ssj = \"$EKS_CLUSTER_NAME\"" -i $ci_default_manifest_values_yaml
yq eval ".indexd.secrets.userdb.gateway = \"$EKS_CLUSTER_NAME\"" -i $ci_default_manifest_values_yaml

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
yq eval ".audit.server.sqs.url = \"$AUDIT_QUEUE_URL\"" -i $ci_default_manifest_values_yaml
yq eval ".ssjdispatcher.ssjcreds.sqsUrl = \"$UPLOAD_QUEUE_URL\"" -i $ci_default_manifest_values_yaml
yq eval ".fence.FENCE_CONFIG_PUBLIC.PUSH_AUDIT_LOGS_CONFIG.aws_sqs_config.sqs_url = \"$AUDIT_QUEUE_URL\"" -i $ci_default_manifest_values_yaml

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
yq eval ".ssjdispatcher.ssjcreds.jobPattern = \"s3://gen3-helm-data-upload-bucket/ci${ENV_PREFIX}/*\"" -i "$ci_default_manifest_values_yaml"
yq eval ".ssjdispatcher.ssjcreds.jobPassword = \"$EKS_CLUSTER_NAME\"" -i $ci_default_manifest_values_yaml
yq eval ".ssjdispatcher.ssjcreds.metadataservicePassword = \"$EKS_CLUSTER_NAME\"" -i $ci_default_manifest_values_yaml

# Add in hostname/namespace for revproxy, ssjdispatcher, hatchery, fence, and manifestservice configuration.
yq eval ".revproxy.ingress.hosts[0].host = \"$HOSTNAME\"" -i $ci_default_manifest_values_yaml
yq eval ".manifestservice.manifestserviceG3auto.hostname = \"$HOSTNAME\"" -i $ci_default_manifest_values_yaml
yq eval ".fence.FENCE_CONFIG_PUBLIC.BASE_URL = \"https://${HOSTNAME}/user\"" -i $ci_default_manifest_values_yaml
yq eval ".ssjdispatcher.gen3Namespace = \"${namespace}\"" -i $ci_default_manifest_values_yaml
sed -i "s|FRAME_ANCESTORS: https://<hostname>|FRAME_ANCESTORS: https://${HOSTNAME}|" $ci_default_manifest_values_yaml

# Remove aws-es-proxy block
yq -i 'del(.aws-es-proxy)' $ci_default_manifest_values_yaml

# Check if sheepdog's fenceUrl key is present and update it
sheepdog_fence_url=$(yq eval ".sheepdog.fenceUrl // \"key not found\"" "$ci_default_manifest_values_yaml")
if [ "$sheepdog_fence_url" != "key not found" ]; then
    echo "Key sheepdog.fenceUrl found in \"$ci_default_manifest_values_yaml\""
    yq eval ".sheepdog.fenceUrl = \"https://$HOSTNAME/user\"" -i "$ci_default_manifest_values_yaml"
fi

# Check if global manifestGlobalExtraValues fenceUrl key is present and update it.
manifest_global_extra_values_fence_url=$(yq eval ".global.manifestGlobalExtraValues.fence_url // \"key not found\"" "$ci_default_manifest_values_yaml")
if [ "$manifest_global_extra_values_fence_url" != "key not found" ]; then
    echo "Key global.manifestGlobalExtraValues.fence_url found in \"$ci_default_manifest_values_yaml\""
    yq eval ".global.manifestGlobalExtraValues.fence_url = \"https://$HOSTNAME/user\"" -i "$ci_default_manifest_values_yaml"
fi

# delete the ssjdispatcher deployment so a new one will get created and use the new configuration file.
kubectl delete deployment -l app=ssjdispatcher -n ${namespace}

# Set env variable for ETL enabled or not
ETL_ENABLED=$(yq '.etl.enabled // "false"' "$ci_default_manifest_values_yaml")
echo "ETL_ENABLED=$ETL_ENABLED" >> "$GITHUB_ENV"

echo $HOSTNAME
install_helm_chart() {
  #For custom helm branch
  if [ "$helm_branch" != "master" ]; then
    git clone --branch "$helm_branch" https://github.com/uc-cdis/gen3-helm.git
    echo "dependency update"
    helm dependency update gen3-helm/helm/gen3
    echo "grep"
    cat $ci_default_manifest_values_yaml | grep -i "elasticsearch:"
    echo "installing helm chart"
    if helm upgrade --install ${namespace} gen3-helm/helm/gen3 --set global.hostname="${HOSTNAME}" -f $ci_default_manifest_values_yaml -n "${NAMESPACE}"; then
      echo "Helm chart installed!"
    else
      return 1
    fi
  else
    helm repo add gen3 https://helm.gen3.org
    helm repo update
    if helm upgrade --install ${namespace} gen3/gen3 --set global.hostname="${HOSTNAME}" -f $ci_default_manifest_values_yaml -n "${NAMESPACE}"; then
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
