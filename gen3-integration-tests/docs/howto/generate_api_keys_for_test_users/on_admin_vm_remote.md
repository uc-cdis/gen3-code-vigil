We use jenkins to run commands from cloud-automation on the admin VM. The jenkins scripts are [here](gen3_ci/jenkins_jobs/)

You can use the following jenkins job to generate the api_keys (the keys are saved as build artifacts):
- For CI and test environments use [jenkins1-job](https://jenkins.planx-pla.net/view/CI%20Jobs/job/generate-api-keys/)
- For dev environments use [jenkins2-job](https://jenkins2.planx-pla.net/job/generate-api-keys/)
