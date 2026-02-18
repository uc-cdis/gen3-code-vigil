# Steps

## 1. Bring up gen3 instance locally
Please refer to [gen3-helm](https://github.com/uc-cdis/gen3-helm) repo

## 2. Generate API keys for all test users
*Note: This assumes that USERYAML block is correctly set up in the values.yaml using the data [here](https://github.com/uc-cdis/gen3-code-vigil/blob/master/gen3-integration-tests/test_data/test_setup/user.yaml)*

Switch to `gen3-integration-tests` directory and execute:

    ```
    ./gen3_ci/scripts/generate_api_keys.sh test_data/test_setup/users.csv <hostname> <namespace>
    ```
*Note: you might need to run `chmod +x ./gen3_ci/scripts/generate_api_keys.sh` once*

The API keys should be saved to `~/.gen3` directory

## 3. Run tests
1. Switch to `gen3-integration-tests` directory
1. Set up the following environment variables in the `.env`file
    ```
    HOSTNAME="<hostname>"
    NAMESPACE="<namespace>"
    ```
Note: Please make sure the usersync job is configured on the environment, as the usersync job is run during pytest setup.
1. Run tests with pytest
    ```
    poetry run pytest --video=retain-on-failure --alluredir allure-results -n auto --dist loadscope
    ```
