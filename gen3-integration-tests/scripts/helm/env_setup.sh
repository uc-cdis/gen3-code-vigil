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

if [ "$setup_type" == "test-env-setup" ] ; then
    # If PR is under test repository, then do nothing
    echo "Setting Up Test PR Env..."
elif [ "$setup_type" == "service-env-setup" ]; then
    # If PR is under a service repository, then update the image for the given service
    echo "Setting Up Service PR Env..."
    # Inputs:
    # service_name - name of service against which PR is run
    # image_name - name of the quay image for the service PR
    service_name="$4"
    image_name="$5"
    yq eval ".${service_name}.image.tag = \"${image_name}\"" -i values.yaml
elif [ "$setup_type" == "manifest-env-setup" ]; then
    # If PR is under a manifest repository, then update the yaml files as needed
    echo "Setting Up Manifest PR Env..."
    # Inputs:
    # ci_default_manifest - name of the folder containing default ci env configuration
    # target_manifest_path - name of the folder containing manifest env configuration
    ci_default_manifest="${4}/values"
    target_manifest_path="${5}/values"
    echo "CI Default Env Configuration Folder Path: ${ci_default_manifest}"
    echo "New Env Configuration Folder Path: ${target_manifest_path}"

    ####################################################################################
    # Check if manifest etl.yaml exists and perform operations on ci etl.yaml
    ####################################################################################
    if [ "$target_manifest_path/etl.yaml" ]; then
        cp "$target_manifest_path/etl.yaml" "$ci_default_manifest/etl.yaml"
    fi

    ####################################################################################
    # Update images for fence from $target_manifest_path/fence.yaml
    ####################################################################################
    image_tag_value=$(yq eval ".fence.image.tag" $target_manifest_path/fence.yaml 2>/dev/null)
    if [ ! -z "$image_tag_value" ]; then
        yq eval ".fence.image.tag = \"$image_tag_value\"" -i $ci_default_manifest/fence.yaml
    fi

    ####################################################################################
    # Update images for guppy from $target_manifest_path/guppy.yaml
    ####################################################################################
    image_tag_value=$(yq eval ".guppy.image.tag" $target_manifest_path/guppy.yaml 2>/dev/null)
    if [ ! -z "$image_tag_value" ]; then
        yq eval ".guppy.image.tag = \"$image_tag_value\"" -i $ci_default_manifest/guppy.yaml
    fi

    ####################################################################################
    # Check if manifest hatchery.yaml exists and perform operations on ci hatchery.yaml
    ####################################################################################
    if [ "$target_manifest_path/hatchery.yaml" ]; then
        cp "$target_manifest_path/hatchery.yaml" "$ci_default_manifest/hatchery.yaml"
    fi

    ####################################################################################
    # Check if manifest portal.yaml exists and perform operations on ci portal.yaml
    ####################################################################################
    if [ "$target_manifest_path/portal.yaml" ]; then
        cp "$target_manifest_path/portal.yaml" "$ci_default_manifest/portal.yaml"
        json_content=$(yq eval '.portal.gitops.json' "$yaml_file")
        modified_json=$(echo "$json_content" | jq 'del(.requiredCerts)')
        yq eval ".portal.gitops.json = $modified_json" "$ci_default_manifest/portal.yaml" > "$ci_default_manifest/updated_gitops.yaml"
        mv "$ci_default_manifest/updated_gitops.yaml" "$ci_default_manifest/portal.yaml"
    fi

    ####################################################################################
    # Make sure the blocks of values.yaml in ci default are in reflection of the blocks
    # of values.yaml in target_manifest_path.
    ####################################################################################
    # Get all the top-level keys from both files
    keys_ci=$(yq eval 'keys' $ci_default_manifest/values.yaml -o=json | jq -r '.[]')
    keys_manifest=$(yq eval 'keys' $target_manifest_path/values.yaml -o=json | jq -r '.[]')

    # Remove blocks from $ci_default_manifest/values.yaml that are not present in $target_manifest_path/values.yaml
    for key in $keys_ci; do
    if ! echo "$keys_manifest" | grep -q "^$key$"; then
        yq eval "del(.$key)" -i $ci_default_manifest/values.yaml
    fi
    done

    # Add blocks from $target_manifest_path/values.yaml that are not present in $ci_default_manifest/values.yaml
    for key in $keys_manifest; do
    if ! echo "$keys_ci" | grep -q "^$key$"; then
        yq eval ". |= . + {\"$key\": $(yq eval .$key $target_manifest_path/values.yaml -o=json)}" -i $ci_default_manifest/values.yaml
    fi
    done

    ####################################################################################
    # Update images for each service from $target_manifest_path/values.yaml
    ####################################################################################
    for key in $keys_manifest; do
    image_tag_value=$(yq eval ".${key}.image.tag" $target_manifest_path/values.yaml 2>/dev/null)
    if [ ! -z "$image_tag_value" ]; then
        yq eval ".${key}.image.tag = \"$image_tag_value\"" -i $ci_default_manifest/values.yaml
    fi
    done

    ############################################################################################################################
    # Perform operations for global and other sections under values.yaml
    ############################################################################################################################
    keys=("global.dictionaryUrl"
     "global.portalApp"
     "global.netpolicy"
     "global.frontendRoot"
     "global.es7"
     "google.enabled"
     "ssjdispatcher.indexing"
     "metadata.useAggMds"
     "metadata.aggMdsNamespace"
     )
    for key in "${keys[@]}"; do
        ci_value=$(yq eval ".$key // \"key not found\"" $ci_default_manifest/values.yaml)
        manifest_value=$(yq eval ".$key // \"key not found\"" $target_manifest_path/values.yaml)
        if [ "$manifest_value" = "key not found" ]; then
            echo "The key '$key' is not present in the Manifest YAML file."
        else
            echo "CI default value of the key '$key' is: $ci_value"
            echo "Manifest value of the key '$key' is: $manifest_value"
            yq eval ".${key} = \"${manifest_value}\"" -i "$ci_default_manifest/values.yaml"
        fi
    done

    # Update mds_url and common_url under metadata if present
    json_content=$(yq eval ".metadata.aggMdsConfig // \"key not found\"" "$ci_default_manifest/values.yaml")
    if [ "$json_content" != "key not found" ]; then
        current_mds_url=$(echo "$json_content" | jq -r ".adapter_commons.gen3.mds_url // \"key not found\"")
        if [ "$current_value" != "key not found" ]; then
            modified_json=$(echo "$json_content" | jq ".adapter_commons.gen3.mds_url = \"https://${namespace}.planx-pla.net/\"")
            yq eval --inplace ".metadata.aggMdsConfig = ${modified_json}" "$ci_default_manifest/values.yaml"
        fi
        current_commons_url=$(echo "$json_content" | jq -r ".adapter_commons.gen3.commons_url // \"key not found\"")
        if [ "$current_value" != "key not found" ]; then
            modified_json=$(echo "$json_content" | jq ".adapter_commons.gen3.commons_url = \"${namespace}.planx-pla.net/\"")
            yq eval --inplace ".metadata.aggMdsConfig = ${modified_json}" "$ci_default_manifest/values.yaml"
        fi
    fi
fi

kubectl delete pvc -l app.kubernetes.io/name=postgresql -n ${{ env.NAMESPACE }}
# add script to check if stuck in terminating and then patch to remove finalizer

echo $HOSTNAME
install_helm_chart() {
  #For custom helm branch
  if [ "$helm_branch" != "master" ]; then
    git clone --branch "$helm_branch" https://github.com/uc-cdis/gen3-helm.git
    helm dependency update gen3-helm/helm/gen3
    if helm upgrade --install ${namespace} gen3-helm/helm/gen3 --set global.hostname="${HOSTNAME}" -f gen3_ci/default_manifest/values/values.yaml -f gen3_ci/default_manifest/values/portal.yaml -f gen3_ci/default_manifest/values/guppy.yaml -f gen3_ci/default_manifest/values/fence.yaml -f gen3_ci/default_manifest/values/etl.yaml -n "${NAMESPACE}"; then
      echo "Helm chart installed!"
    else
      return 1
    fi
  else
    helm repo add gen3 https://helm.gen3.org
    helm repo update
    if helm upgrade --install ${namespace} gen3/gen3 --set global.hostname="${HOSTNAME}" -f gen3_ci/default_manifest/values/values.yaml -f gen3_ci/default_manifest/values/portal.yaml -f gen3_ci/default_manifest/values/guppy.yaml -f gen3_ci/default_manifest/values/fence.yaml -f gen3_ci/default_manifest/values/etl.yaml -n "${NAMESPACE}"; then
      echo "Helm chart installed!"
    else
      return 1
    fi
  fi
  return 0
}

ci_es_indices_setup() {
  echo "Setting up ES port-forward..."
  kubectl delete pvc -l app=gen3-elasticsearch-master -n ${namespace}
  kubectl wait --for=condition=ready pod -l app=gen3-elasticsearch-master --timeout=5m -n ${namespace}

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

# kubectl delete pvc -l app.kubernetes.io/name=postgresql -n ${namespace}

# 🚀 Run the helm install and then wait for pods if successful
if install_helm_chart; then
  ci_es_indices_setup
  wait_for_pods_ready
else
  echo "❌ Helm chart installation failed"
  exit 1
fi

kubectl delete job usersync-manual
kubectl create job --from=cronjob/usersync usersync-manual -n ${namespace}
kubectl wait --for=condition=complete job/usersync-manual --namespace=${namespace} --timeout=5m
