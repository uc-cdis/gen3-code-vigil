#!/bin/bash
# ./generate_api_keys.sh path/to/user.csv hostname
# Script to generate api keys for all test users.
# We first generate an access token from within fence pod and use that to generate api key.
USERS_FILE=$1
HOSTNAME=$2
# Skip the header and process the CSV
tail -n +2 "$USERS_FILE" | while IFS="," read -r username email; do
    echo "Processing user $username - $email ..."
    ACCESS_TOKEN=$(kubectl exec -c fence $(kubectl get pods -l app=fence -o jsonpath="{.items[0].metadata.name}") -- fence-create token-create --scopes openid,user,fence,data,credentials,google_service_account --type access_token --username $email 2>/dev/null | tail -1)
    echo "ACCESS TOKEN: $ACCESS_TOKEN"
    curl -s -X POST "https://$HOSTNAME/user/credentials/api" -H "Authorization: bearer $ACCESS_TOKEN" -H "Content-Type: application/json" -H "Accept: aplication/json" > $HOME/.gen3/${HOSTNAME}_${username}.json 2>/dev/null
    cat $HOME/.gen3/${HOSTNAME}_${username}.json
    echo "Saved API key in file ~/.gen3/${HOSTNAME}_${username}.json"
done
