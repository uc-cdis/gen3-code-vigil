# Notes
## Steps
1. Bring up gen3 locally. Please refer [gen3-helm](https://github.com/uc-cdis/gen3-helm) repo
1. Create required fence clients
1. Run usersync (test users are configured in the USERYAML block of values.yaml)
1. Generate API keys for all test users

# References
1.

# Notes
1. Generate access token
    ```
    kubectl exec -c fence $(kubectl get pods -l app=fence -o jsonpath="{.items[0].metadata.name}") -- fence-create token-create --scopes openid,user,fence,data,credentials,google_service_account --type access_token --exp ${exp} --username ${username} | tail -1 >> ${username}_access_token.txt
    ```
1. Generate api key using the access token generated in the previous step
   ```
   curl -s -X POST "$NAMESPACE/user/credentials/api" -H "Authorization: bearer $accessToken" -H "Content-Type: application/json" -H "Accept: aplication/json"
   ```
