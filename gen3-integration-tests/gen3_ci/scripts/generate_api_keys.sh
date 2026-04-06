#!/bin/bash
# ./generate_api_keys.sh path/to/user.csv hostname
# Script to generate API keys for all test users.
# Generates an access token from the fence pod and uses that to generate an API key.

set -euo pipefail  # Exit on errors, undefined variables, and failed pipes.

# Validate arguments
if [[ $# -ne 4 ]]; then
    echo "Usage: $0 <path-to-user.csv> <hostname> <namespace> <hostname protocol>"
    exit 1
fi

USERS_FILE=$1
HOSTNAME=$2
NAMESPACE=$3
HOSTNAME_PROTOCOL=$4

# Check if the users file exists
if [[ ! -f "$USERS_FILE" ]]; then
    echo "Error: Users file '$USERS_FILE' not found!"
    exit 1
fi

# Create output directory if it doesn't exist
OUTPUT_DIR="$HOME/.gen3"
mkdir -p "$OUTPUT_DIR"
chmod -R 755 "$OUTPUT_DIR"

# echo "NAMESPACE:" $NAMESPACE
# # echo "kubectl get namespaces:"
# # kubectl get namespaces
# echo "============"
# echo "kubectl get pods -n default:"
# echo "1============"
# kubectl get pods -n default
# echo "1============"
# echo "kubectl get pods -n $NAMESPACE:"
# echo "2============"
# kubectl get pods -n "$NAMESPACE"
# echo "2============"

# Get running fence pod
FENCE_POD=$(kubectl get pods -l app=fence -o json -n "$NAMESPACE" | jq -r '.items[0].metadata.name // empty')

if [[ -z "$FENCE_POD" ]]; then
    echo "Error: Could not find a running fence pod."
    exit 1
fi

# Process the CSV file (skip the header)
tail -n +2 "$USERS_FILE" | while IFS="," read -r username email; do
    echo "Processing user: $username - $email ..."

    # Generate an access token
    kubectl -n "$NAMESPACE" exec -c fence "$FENCE_POD" -- fence-create token-create --scopes openid,user,fence,data,credentials,google_service_account --type access_token --username "$email"
    ACCESS_TOKEN=$(kubectl -n "$NAMESPACE" exec -c fence "$FENCE_POD" -- fence-create token-create --scopes openid,user,fence,data,credentials,google_service_account --type access_token --username "$email" 2>/dev/null | tail -1)

    # Validate access token
    if [[ -z "$ACCESS_TOKEN" ]]; then
        echo "Error: Failed to generate access token for $email"
        exit 1
    fi

    # echo '----- _status'
    # # curl -o "$OUTPUT_DIR/status" -w "%{http_code}" http://localhost/user/_status
    # # cat $OUTPUT_DIR/status
    # curl -o "$OUTPUT_DIR/status" -w "%{http_code}" http://localhost:8000/user/_status
    # cat $OUTPUT_DIR/status
    # curl -o "$OUTPUT_DIR/status" -w "%{http_code}" $HOSTNAME_PROTOCOL://$HOSTNAME/user/_status
    # cat $OUTPUT_DIR/status

    # exit 1

    # Request API key
    RESPONSE=$(curl -o "$OUTPUT_DIR/${NAMESPACE}_${username}.json" -w "%{http_code}" -X POST "$HOSTNAME_PROTOCOL://$HOSTNAME/user/credentials/api" \
        -H "Authorization: bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json")

    echo '$HOSTNAME =' $HOSTNAME
    # echo $RESPONSE

    curl -o "$OUTPUT_DIR/status" -w "%{http_code}" $HOSTNAME_PROTOCOL://$HOSTNAME/user/_status
    cat $OUTPUT_DIR/status
    curl -o "$OUTPUT_DIR/version" -w "%{http_code}" $HOSTNAME_PROTOCOL://$HOSTNAME/user/_version
    cat $OUTPUT_DIR/version

    # kubectl get pods -n $NAMESPACE


    # Validate API response
    if [[ "$RESPONSE" -ne 200 ]]; then
        echo "Error: Failed to generate API key for $email (HTTP status: $RESPONSE). Fence logs (all replicas):"
        kubectl logs -l app=fence -n "${NAMESPACE}" --tail 30
        echo "Revproxy logs (all replicas):"
        kubectl get pods -l app=revproxy -n "${NAMESPACE}"
        kubectl logs -l app=revproxy -n "${NAMESPACE}" --tail 30
        exit 1
    fi

    echo "Saved API key in file: $OUTPUT_DIR/${NAMESPACE}_${username}.json"
done

echo "API key generation completed successfully!"
