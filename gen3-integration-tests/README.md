# Running tests locally

## Setup

### Identify GEN3_INSTANCE_TYPE
The integration tests can be run on Gen3 instances hosted using cloud-automation or helm. Since the mechanisms for running admin tasks varies for both, we must specify this for executing tests correctly. The following values are accepted:
- ADMINVM_REMOTE (for instances hosted on a remote admin VM using cloud-automation)
- HELM_LOCAL (for instances hosted locally using helm)

### Test user credentials
The code supports running different steps as different users. Please see pytest_configure method in conftest.py for details.

The test users required to run the tests are listed [here](test_data/test_setup/users.csv)

You can use the following jenkins job to generate the api_keys (the keys are saved as build artifacts):
- For CI and test environments use [jenkins1-job](https://jenkins.planx-pla.net/view/CI%20Jobs/job/generate-api-keys/)
- For dev environments use [jenkins2-job](https://jenkins2.planx-pla.net/job/generate-api-keys/)

### Running gen3 admin tasks
We use jenkins for running tasks like metadata-aggregate-sync, etl etc.
Create a .env file under `gen3-code-vigil/gen3-integration-tests` with the values:

```
JENKINS_URL="https://jenkins.planx-pla.net"
JENKINS_USERNAME=PlanXCyborg
JENKINS_PASSWORD=<Jenkins API Token>
CI_TEST_ORCID_USERID=<ORCID Username>
CI_TEST_ORCID_PASSWORD=<ORCID Password>
CI_TEST_RAS_USERID=<RAS Username>
CI_TEST_RAS_PASSWORD=<RAS Password>
CI_TEST_RAS_2_USERID=<RAS Username>
CI_TEST_RAS_2_PASSWORD=<RAS Password>
```
The Jenkins API token, ORCID creds and RAS creds can be obtained from Keeper.

## Running tests
Switch to `gen3-code-vigil/gen3-integration-tests` and run the commands:
```
mkdir output
poetry install
```
Then (please note that these are example values, please replace with the right ones):
```
GEN3_INSTANCE_TYPE="ADMINVM_REMOTE" HOSTNAME="jenkins-brain.planx-pla.net" poetry run pytest --alluredir allure-results -n auto --dist loadscope
```
The kubernetes namespace is required for Gen3 admin tasks. It is assumed to be the first part of the hostname (`jenkins-brain` in the example above).
If it is different it must be explicitly defined, like
```
GEN3_INSTANCE_TYPE="ADMINVM_REMOTE" HOSTNAME="jenkins-brain.planx-pla.net" NAMESPACE="something_else" poetry run pytest --alluredir allure-results -n auto --dist loadscope
```

We use [allure-pytest](https://pypi.org/project/allure-pytest/). The report can be viewed by running `allure serve allure-results`

We can set TESTED_ENV to the enviroment being actually tested. This is useful when we replicate the configuration of the tested environment in the dev / test environment for testing or development. We can then run the tests by executing
```
GEN3_INSTANCE_TYPE="ADMINVM_REMOTE" TESTED_ENV="healdata.org" HOSTNAME="jenkins-brain.planx-pla.net" poetry run pytest --html=output/report.html --self-contained-html -n auto --dist loadscope
```

`-n auto` comes from [python-xdist](https://pypi.org/project/pytest-xdist/). We run test classes / suties in parallel using the `--dist loadscope`. To use this feature it is imperative that the test suites are designed to be independent and idempotent.

Markers and `-m` flag can be used to specify what tests should or should not run. For example, `-m wip` selects only tests with marker `wip` and `-m not wip` skips tests with marker `wip`. Read more about marking tests [here](https://docs.pytest.org/en/7.1.x/example/markers.html)

# Running tests in continuous integration pipeline
All the code pertaining to using the repo in CI is at `gen3-code-vigil/gen3-integration-tests/gen3_ci`. Jenkins is used for setting up the test environments and interacting with them.
- `jenkins-jobs` directory contains the groovy scripts used by the jenkins jobs.
- `scripts` directory contains python scripts used in the github actions workflow.

# Designing tests

## Design principles (not optional)
- The test suites must be independent and idempotent. This is essential since we run test classes in parallel by using xdist (loadscope).
- All tests should be able to run anywhere (locally / CI) without changing test code.
- Debugging must be done locally, not in CI pipeline.
- Documentation is essential. Code is incomplete without it.
- Avoid hard waits. Test should wait for application state, not otherwise.
- Tag tests appropriately.
- Add test steps as docstrings in the test for understanding the purpose of the test easily.
- Mark in-progress tests with marker `wip` to prevent CI pipeline from breaking when incomplete test code is pushed to repo.

## Code organization
Test code is organized into 4 directories:  `services`, `tests`, `test-data` and `utils`.
- `pages` contains endpoints, locators and methods specific to each page in the portal. There is a separate module for each page.
- `scripts` contains standalone helper scripts to assist in setting up the environment.
- `services` contains the endpoints and methods specific to each service. There is a separate module for each service.
- `test_data` contains the test data.
- `tests` contains the tests written in pytest. Tests are further separated into api tests and gui tests.
- `utils` contains utility and helper functions.
