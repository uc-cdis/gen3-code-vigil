#!/bin/bash

gen3_logs_snapshot_container() {
  local podName
  local containerName

  if [[ $# -lt 1 ]]; then
    echo "must pass podName argument, containerName is optional"
    return 1
  fi
  podName="$1"
  shift
  containerName=""
  if [[ $# -gt 0 ]]; then
    containerName="$1"
    shift
  fi
  local fileName
  fileName="${podName}.${containerName}.log"
  if kubectl logs "$podName" -c "$containerName" -n pr-161 --limit-bytes 250000 > "$fileName" && gzip -f "$fileName"; then
    echo "${fileName}.gz"
    return 0
  fi
  return 1
}

#
# Snapshot all the pods
#
# For each pod for which we can list the containers, get the pod name and get its list of containers
# (container names + initContainers names). Diplay them as lines of "<pod name>  <container name>".
kubectl get pods -o json -n pr-161 | \
  jq -r '.items | map(select(.status.phase != "Pending" and .status.phase != "Unknown")) | .[] | .metadata.name as $pod | (.spec.containers + .spec.initContainers) | map(select(.name != "pause" and .name != "jupyterhub")) | .[] | {pod: $pod, cont: .name} | "\(.pod)  \(.cont)"' | \
  while read -r line; do
    gen3_logs_snapshot_container $line
  done
