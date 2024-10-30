# Steps

## 1. Bring up gen3 instance locally
Please refer to [gen3-helm](https://github.com/uc-cdis/gen3-helm) repo

## 2. Generate API keys for all test users
*Note: This assumes that USERYAML block is correctly set up in the values.yaml used to start the instance.*

Switch to `gen3-integration-tests` directory and execute:

    ```
    ./scripts/helm/generate_api_keys.sh test_data/test_setup/users.csv <hostname>
    ```
*Note: you might need to run `chmod +x ./scripts/helm/generate_api_keys.sh` once*

The API keys should be saved to `~/.gen3` directory

## 3. Run tests
1. Switch to `gen3-integration-tests` directory
1. Set up the following environment variables in the `.env`file
    ```
    GEN3_INSTANCE_TYPE="HELM_LOCAL"
    HOSTNAME="<hostname>"
    JENKINS_URL=<Jenkins Host>
    JENKINS_USERNAME=<Jenkins Username>
    JENKINS_PASSWORD=<Jenkins API Token>
    ```
1. Run tests with pytest
    ```
    poetry run pytest --alluredir allure-results -n auto --dist loadscope
    ```

## (WIP)
We can set TESTED_ENV to the enviroment being actually tested. This is useful when we replicate the configuration of the tested environment in the dev / test environment for testing or development. We can then run the tests by:
1. Setting up TESTED_ENV in `.env` file, e.g.,
    ```
    GEN3_INSTANCE_TYPE="HELM_LOCAL"
    HOSTNAME="<hostname>"
    JENKINS_URL=<Jenkins Host>
    JENKINS_USERNAME=<Jenkins Username>
    JENKINS_PASSWORD=<Jenkins API Token>
    TESTED_ENV="healdata.org"
    ```
1. Run tests with pytest
    ```
    poetry run pytest --alluredir allure-results -n auto --dist loadscope
    ```
