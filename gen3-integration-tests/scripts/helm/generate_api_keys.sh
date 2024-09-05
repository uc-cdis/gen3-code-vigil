# Script to generate api keys for all test users. We first generate an access token from within fence pod and use that to generate api key

users=("cdis.autotest@gmail.com" "ctds.indexing.test@gmail.com" "dummy-one@planx-pla.net" "smarty-two@planx-pla.net" "dcf-integration-test-0@planx-pla.net" "dcf-integration-test-1@planx-pla.net" "dcf-integration-test-2@planx-pla.net")

for user in "${users[@]}"; do
kubectl exec -c fence $(kubectl get pods -l app=fence -o jsonpath="{.items[0].metadata.name}") -- fence-create token-create --scopes openid,user,fence,data,credentials,google_service_account --type access_token --exp ${exp} --username ${user} | tail -1 >> ${user}_access_token.txt
curl -s -X POST "$NAMESPACE/user/credentials/api" -H "Authorization: bearer $accessToken" -H "Content-Type: application/json" -H "Accept: aplication/json"
