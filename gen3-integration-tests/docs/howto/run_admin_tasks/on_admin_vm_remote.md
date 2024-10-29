We use jenkins to run commands from cloud-automation on the admin VM. The jenkins scripts are [here](gen3_ci/jenkins_jobs/)

Update the .env file under `gen3-code-vigil/gen3-integration-tests` with the values:
```
JENKINS_URL=<Jenkins Host>
JENKINS_USERNAME=<Jenkins Username>
JENKINS_PASSWORD=<Jenkins API Token>
```
The Jenkins API token, ORCID creds and RAS creds can be obtained from our internal password store.
