#!/bin/bash

# This script helps setup the gen3-helm env for running intergration tests.
# It contains 3 blocks, test-env-setup, service-env-setup and manifest-env-setup.

# Inputs:
# namespace - namespace aginst which env is setup
# setup_type - type of setup being performed
# service_name - name of service against which PR is run
# image_name - name of the quay image for the service PR

namespace="$1"
setup_type="$2"

if [ "$setup_type" == "test-env-setup" ] ; then
    echo "Setting Up Test PR Env..."
elif [ "$setup_type" == "service-env-setup" ]; then
    echo "Setting Up Service PR Env..."
    service_name="$3"
    image_name="$4"
    echo "yq eval ".${service_name}.image.tag = \"${image_name}\"" -i values_ec2.yaml"
    yq eval ".${service_name}.image.tag = \"${image_name}\"" -i values_ec2.yaml
elif [ "$setup_type" == "manifest-env-setup" ]; then
    echo "Setting Up Manifest PR Env..."
fi

# Perform general steps to bring up the env after the values are set.
helm upgrade --install gen3 gen3/gen3 -f values_ec2.yaml
sleep 60
kubectl wait --for=condition=Ready pod -l app=gen3-elasticsearch-master --namespace=${namespace} --timeout=5m
kubectl create job --from=cronjob/usersync usersync-manual -n ${namespace}
kubectl wait --for=condition=complete job/usersync-manual --namespace=${namespace} --timeout=5m
