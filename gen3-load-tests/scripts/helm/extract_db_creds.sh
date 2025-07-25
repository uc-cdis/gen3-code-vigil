# Extract database credentials for services to be used in values.yaml for persistence.
# We must first enable persistence and start gen3 using helm. Once it is up and running,
# use this script to extract creds and save the same in values.yaml. Next time gen3 is
# launched with helm, we should see the data that is persisted.

echo "arborist:" > dbcreds.txt
echo "  postgres:" >> dbcreds.txt
echo "    dbCreate: true" >> dbcreds.txt
username=`kubectl get secret arborist-dbcreds -o json | jq -r '.data.username' | base64 --decode`
echo "    username: $username" >> dbcreds.txt
password=`kubectl get secret arborist-dbcreds -o json | jq -r '.data.password' | base64 --decode`
echo "    password: $password" >> dbcreds.txt
echo "" >> dbcreds.txt

echo "audit:" >> dbcreds.txt
echo "  postgres:" >> dbcreds.txt
echo "    dbCreate: true" >> dbcreds.txt
username=`kubectl get secret audit-dbcreds -o json | jq -r '.data.username' | base64 --decode`
echo "    username: $username" >> dbcreds.txt
password=`kubectl get secret audit-dbcreds -o json | jq -r '.data.password' | base64 --decode`
echo "    password: $password" >> dbcreds.txt
echo "" >> dbcreds.txt

echo "fence:" >> dbcreds.txt
echo "  postgres:" >> dbcreds.txt
echo "    dbCreate: true" >> dbcreds.txt
username=`kubectl get secret fence-dbcreds -o json | jq -r '.data.username' | base64 --decode`
echo "    username: $username" >> dbcreds.txt
password=`kubectl get secret fence-dbcreds -o json | jq -r '.data.password' | base64 --decode`
echo "    password: $password" >> dbcreds.txt
echo "" >> dbcreds.txt

echo "indexd:" >> dbcreds.txt
echo "  postgres:" >> dbcreds.txt
echo "    dbCreate: true" >> dbcreds.txt
username=`kubectl get secret indexd-dbcreds -o json | jq -r '.data.username' | base64 --decode`
echo "    username: $username" >> dbcreds.txt
password=`kubectl get secret indexd-dbcreds -o json | jq -r '.data.password' | base64 --decode`
echo "    password: $password" >> dbcreds.txt
echo "" >> dbcreds.txt

echo "metadata:" >> dbcreds.txt
echo "  postgres:" >> dbcreds.txt
echo "    dbCreate: true" >> dbcreds.txt
username=`kubectl get secret metadata-dbcreds -o json | jq -r '.data.username' | base64 --decode`
echo "    username: $username" >> dbcreds.txt
password=`kubectl get secret metadata-dbcreds -o json | jq -r '.data.password' | base64 --decode`
echo "    password: $password" >> dbcreds.txt
echo "" >> dbcreds.txt

echo "peregrine:" >> dbcreds.txt
echo "  postgres:" >> dbcreds.txt
echo "    dbCreate: true" >> dbcreds.txt
username=`kubectl get secret peregrine-dbcreds -o json | jq -r '.data.username' | base64 --decode`
echo "    username: $username" >> dbcreds.txt
password=`kubectl get secret peregrine-dbcreds -o json | jq -r '.data.password' | base64 --decode`
echo "    password: $password" >> dbcreds.txt
echo "" >> dbcreds.txt

echo "sheepdog:" >> dbcreds.txt
echo "  postgres:" >> dbcreds.txt
echo "    dbCreate: true" >> dbcreds.txt
username=`kubectl get secret sheepdog-dbcreds -o json | jq -r '.data.username' | base64 --decode`
echo "    username: $username" >> dbcreds.txt
password=`kubectl get secret sheepdog-dbcreds -o json | jq -r '.data.password' | base64 --decode`
echo "    password: $password" >> dbcreds.txt
echo "" >> dbcreds.txt

echo "wts:" >> dbcreds.txt
echo "  postgres:" >> dbcreds.txt
echo "    dbCreate: true" >> dbcreds.txt
username=`kubectl get secret wts-dbcreds -o json | jq -r '.data.username' | base64 --decode`
echo "    username: $username" >> dbcreds.txt
password=`kubectl get secret wts-dbcreds -o json | jq -r '.data.password' | base64 --decode`
echo "    password: $password" >> dbcreds.txt
