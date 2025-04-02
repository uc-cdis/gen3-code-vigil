#!/bin/bash

# This script helps setup the gen3-helm env for running intergration tests.
# It contains 3 blocks, test-env-setup, service-env-setup and manifest-env-setup.

# Inputs:
# namespace - namespace aginst which env is setup
# setup_type - type of setup being performed

namespace="$1"
setup_type="$2"

if [ "$setup_type" == "test-env-setup" ] ; then
    # If PR is under test repository, then do nothing
    echo "Setting Up Test PR Env..."
elif [ "$setup_type" == "service-env-setup" ]; then
    # If PR is under a service repository, then update the image for the given service
    echo "Setting Up Service PR Env..."
    # Inputs:
    # service_name - name of service against which PR is run
    # image_name - name of the quay image for the service PR
    service_name="$3"
    image_name="$4"
    yq eval ".${service_name}.image.tag = \"${image_name}\"" -i values.yaml
elif [ "$setup_type" == "manifest-env-setup" ]; then
    # If PR is under a manifest repository, then update the yaml files as needed
    echo "Setting Up Manifest PR Env..."
    # Inputs:
    # cdis_manifest - name of the folder containing default ci env configuration
    # temp_cdis_manifest - name of the folder containing manifest env configuration
    cdis_manifest="${3}/unfunded/gen3.datacommons.io/values"
    temp_cdis_manifest="${4}/unfunded/diseasedatahub.org/values"
    echo "CI Default Env Configuration Folder Path: ${cdis_manifest}"
    echo "New Env Configuration Folder Path: ${temp_cdis_manifest}"

    ###############################################################################
    # Make sure the blocks of values.yaml in cdis_manifest are in reflection of
    # the blocks of values.yaml in temp_cdis_manifest.
    ###############################################################################
    # Get all the top-level keys from both files
    keys_ci=$(yq eval 'keys' $cdis_manifest/values.yaml -o=json | jq -r '.[]')
    keys_manifest=$(yq eval 'keys' $temp_cdis_manifest/values.yaml -o=json | jq -r '.[]')

    # Remove blocks from $cdis_manifest/values.yaml that are not present in $temp_cdis_manifest/values.yaml
    for key in $keys_ci; do
    if ! echo "$keys_manifest" | grep -q "^$key$"; then
        yq eval "del(.$key)" -i $cdis_manifest/values.yaml
    fi
    done

    # Add blocks from $temp_cdis_manifest/values.yaml that are not present in $cdis_manifest/values.yaml
    for key in $keys_manifest; do
    if ! echo "$keys_ci" | grep -q "^$key$"; then
        yq eval ". |= . + {\"$key\": $(yq eval .$key $temp_cdis_manifest/values.yaml -o=json)}" -i $cdis_manifest/values.yaml
    fi
    done

    ###############################################################################
    # Update images for each service from $temp_cdis_manifest/values.yaml
    ###############################################################################
    for key in $keys_manifest; do
    image_tag_value=$(yq eval ".${key}.image.tag" $temp_cdis_manifest/values.yaml 2>/dev/null)
    if [ ! -z "$image_tag_value" ]; then
        yq eval ".${key}.image.tag = \"$image_tag_value\"" -i $cdis_manifest/values.yaml
    fi
    done

    ###############################################################################
    # Perform operations for global and other sections under values.yaml
    ###############################################################################
    keys=("global.dictionaryUrl"
     "global.portalApp"
     "global.netpolicy"
     "global.frontendRoot"
     "global.es7"
     "google.enabled"
     "ssjdispatcher.indexing"
     )
    for key in "${keys[@]}"; do
        ci_value=$(yq eval ".$key // \"key not found\"" $cdis_manifest/values.yaml)
        manifest_value=$(yq eval ".$key // \"key not found\"" $temp_cdis_manifest/values.yaml)
        if [ "$manifest_value" = "key not found" ]; then
            echo "The key '$key' is not present in the Manifest YAML file."
        else
            echo "CI default value of the key '$key' is: $ci_value"
            echo "Manifest value of the key '$key' is: $manifest_value"
        fi
    done

    ###############################################################################
    # Check if manifest portal.yaml exists and perform operations on ci portal.yaml
    ###############################################################################
    if [[ -f $temp_cdis_manifest/portal.yaml ]]; then
        # Update the image tag
        image_tag_value=$(yq eval ".portal.image.tag" $temp_cdis_manifest/portal.yaml 2>/dev/null)
        yq eval ".portal.image.tag = \"$image_tag_value\"" -i $cdis_manifest/portal.yaml
        # Update the gitops json
        gitops_json_value=$(yq eval ".portal.gitops.json" $temp_cdis_manifest/portal.yaml 2>/dev/null)
        yq eval ".portal.gitops.json = \"$gitops_json_value\"" -i $cdis_manifest/portal.yaml
    fi
fi

# Perform general steps to bring up the env after the values are set.
# helm upgrade --install gen3 gen3/gen3 -f values.yaml
# sleep 60
# kubectl wait --for=condition=Ready pod -l app=gen3-elasticsearch-master --namespace=${namespace} --timeout=5m
# kubectl create job --from=cronjob/usersync usersync-manual -n ${namespace}
# kubectl wait --for=condition=complete job/usersync-manual --namespace=${namespace} --timeout=5m
