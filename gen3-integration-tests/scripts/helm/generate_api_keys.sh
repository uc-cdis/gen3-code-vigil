#!/bin/bash
# ./generate_api_keys.sh path/to/user.csv hostname
# Script to generate API keys for all test users.
# Generates an access token from the fence pod and uses that to generate an API key.

set -euo pipefail  # Exit on errors, undefined variables, and failed pipes.

# Validate arguments
if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <path-to-user.csv> <hostname>"
    exit 1
fi

USERS_FILE=$1
HOSTNAME=$2

# Check if the users file exists
if [[ ! -f "$USERS_FILE" ]]; then
    echo "Error: Users file '$USERS_FILE' not found!"
    exit 1
fi

# Create output directory if it doesn't exist
OUTPUT_DIR="$HOME/.gen3"
mkdir -p "$OUTPUT_DIR"

# Get the first fence pod name
FENCE_POD=$(kubectl get pods -l app=fence -o jsonpath="{.items[0].metadata.name}")
if [[ -z "$FENCE_POD" ]]; then
    echo "Error: Could not find a running fence pod."
    exit 1
fi

# Process the CSV file (skip the header)
tail -n +2 "$USERS_FILE" | while IFS="," read -r username email; do
    echo "Processing user: $username - $email ..."

    # Generate an access token
    ACCESS_TOKEN=$(kubectl exec -c fence "$FENCE_POD" -- fence-create token-create --scopes openid,user,fence,data,credentials,google_service_account --type access_token --username "$email" 2>/dev/null | tail -1)

    # Validate access token
    if [[ -z "$ACCESS_TOKEN" ]]; then
        echo "Error: Failed to generate access token for $email"
        exit 1
    fi

    # Request API key
    RESPONSE=$(curl -s -o "$OUTPUT_DIR/${HOSTNAME}_${username}.json" -w "%{http_code}" -X POST "https://$HOSTNAME/user/credentials/api" \
        -H "Authorization: bearer $ACCESS_TOKEN" \
        -H "Content-Type: application/json" \
        -H "Accept: application/json")

    # Validate API response
    if [[ "$RESPONSE" -ne 200 ]]; then
        echo "Error: Failed to generate API key for $email (HTTP status: $RESPONSE)"
        exit 1
    fi

    echo "Saved API key in file: $OUTPUT_DIR/${HOSTNAME}_${username}.json"
done

echo "API key generation completed successfully!"
