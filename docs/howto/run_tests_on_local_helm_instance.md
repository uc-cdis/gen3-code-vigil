# Steps

## 1. Bring up gen3 instance locally
Please refer to [gen3-helm](https://github.com/uc-cdis/gen3-helm) repo

## 2. Run usersync

## 3. Generate API keys for all test users
Switch to `gen3-integration-tests` directory and execute
```
./scripts/helm/generate_api_keys.sh test_data/test_setup/users.csv <hostname>
```
Note: you migh need to run `chmod +x ./scripts/helm/generate_api_keys.sh` once

## 4. Run tests
Switch to `gen3-integration-tests` directory and execute
```
GEN3_INSTANCE_TYPE="HELM_LOCAL" HOSTNAME="<hostname>" poetry run pytest --alluredir allure-results -n auto --dist loadscope
```
