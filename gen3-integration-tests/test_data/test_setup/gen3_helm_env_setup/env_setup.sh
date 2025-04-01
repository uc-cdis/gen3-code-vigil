#!/bin/bash

# This script helps setup the gen3-helm env for running intergration tests.
# It contains 3 blocks, test-env-setup, service-env-setup and manifest-env-setup.

# Inputs:
# namespace - namespace aginst which env is setup
# setup_type - type of setup being performed

namespace="$1"
setup_type="$2"

# If PR is under test repository, then do nothing
if [ "$setup_type" == "test-env-setup" ] ; then
    echo "Setting Up Test PR Env..."
# If PR is under a service repository, then update the image for the given service
elif [ "$setup_type" == "service-env-setup" ]; then
    # Inputs:
    # service_name - name of service against which PR is run
    # image_name - name of the quay image for the service PR
    echo "Setting Up Service PR Env..."
    service_name="$3"
    image_name="$4"
    echo "yq eval ".${service_name}.image.tag = \"${image_name}\"" -i values.yaml"
    yq eval ".${service_name}.image.tag = \"${image_name}\"" -i values.yaml
# If PR is under a manifest repository, then update the yaml files as needed
elif [ "$setup_type" == "manifest-env-setup" ]; then
    echo "Setting Up Manifest PR Env..."
fi

# Perform general steps to bring up the env after the values are set.
helm upgrade --install gen3 gen3/gen3 -f values.yaml
sleep 60
kubectl wait --for=condition=Ready pod -l app=gen3-elasticsearch-master --namespace=${namespace} --timeout=5m
kubectl create job --from=cronjob/usersync usersync-manual -n ${namespace}
kubectl wait --for=condition=complete job/usersync-manual --namespace=${namespace} --timeout=5m
