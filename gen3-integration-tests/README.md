# Running tests locally

## Setup

### Test user credentials
The code supports running different steps as different users. Please see pytest_configure method in conftest.py for details.

The users required to run the tests are:
- `main_account` is the default user. Save API key for that user as `<namespace>_main_account.json` in `~/.gen3` directory. For example, `qa-dcp_main_account.json`
- `indexing_account` is the indexing_admin user. Save the API key as `<namespace>_indexing_account.json` in `~/.gen3` directory.

You can use the following jenkins job to generate the api_keys (the keys are saved as build artifacts):
- If `NAMESPACE` is on `qaplanetv1` use [jenkins1-job](https://jenkins.planx-pla.net/view/CI%20Jobs/job/generate-api-keys/)
- If it is on `devplanetv2` use [jenkins2-job](https://jenkins2.planx-pla.net/job/generate-api-keys/)

### Running gen3 admin tasks
We use jenkins for running tasks like metadata-aggregate-sync, etl etc.
Create a .env file under `gen3-code-vigil/gen3-integration-tests` with the values:

```
JENKINS_URL="https://jenkins.planx-pla.net"
JENKINS_USERNAME=PlanXCyborg
JENKINS_PASSWORD=<Jenkins API Token>
```
The Jenkins API token can be obtained from Keeper.

## Running tests
Switch to `gen3-code-vigil/gen3-integration-tests` and run the command:
```
poetry install
```
Then:
```
HOSTNAME="jenkins-brain.planx-pla.net" poetry run pytest --html=output/report.html --self-contained-html -n auto --dist loadscope
```
The kubernetes namespace is required for Gen3 admin tasks. It is assumed to be the first part of the hostname (`jenkins-brain` in the example above).
If it is different it must be explicitly defined, like
```
HOSTNAME="jenkins-brain.planx-pla.net" NAMESPACE="something_else" poetry run pytest --html=output/report.html --self-contained-html -n auto --dist loadscope
```

We can set TESTED_ENV to the enviroment being actually tested. This is useful when we replicate the configuration of the tested environment in the dev / test environment for testing or development. We can then run the tests by executing
```
TESTED_ENV="healdata.org" HOSTNAME="jenkins-brain.planx-pla.net" poetry run pytest --html=output/report.html --self-contained-html -n auto --dist loadscope
```

`-n auto` comes from [python-xdist](https://pypi.org/project/pytest-xdist/). We run test classes / suties in parallel using the `--dist loadscope`. To use this feature it is imperative that the test suites are designed to be independent and idempotent.

Markers and `-m` flag can be used to specify what tests should or should not run. For example, `-m wip` selects only tests with marker `wip` and `-m not wip` skips tests with marker `wip`. Read more about marking tests [here](https://docs.pytest.org/en/7.1.x/example/markers.html)

# Running tests in continuous integration pipeline
All the code pertaining to using the repo in CI is at `gen3-code-vigil/gen3-integration-tests/gen3_ci`. Jenkins is used for setting up the test environments and interacting with them.
- `jenkins-jobs` directory contains the groovy scripts used by the jenkins jobs.
- `scripts` directory contains python scripts used in the github actions workflow.

# Designing tests

## Design principles (not optional)
- The tests must be independent and idempotent. This is essential since we run tests in parallel.
- All tests should be able to run anywhere (locally / CI) without changing test code.
- Debugging must be done locally, not in CI pipeline.
- Documentation is important. Code is incomplete without it.
- Avoid hard waits. Test should wait for application state, not otherwise.
- Tag tests appropriately.
- Add test steps as docstrings in the test for understanding the purpose of the test easily.
- Mark in-progress tests with marker `wip` to prevent CI pipeline from breaking when incomplete test code is pushed to repo.

## Code organization
Test code is organized into 4 directories:  `services`, `tests`, `test-data` and `utils`.
- `pages` contains endpoints, locators and methods specific to each page in the portal. There is a separate module for each page.
- `services` contains the endpoints and methods specific to each service. There is a separate module for each service.
- `tests` contains the tests written in pytest. Tests are further separated into api tests and gui tests.
- `test-data` contains the test data.
- `utils` contains utility and helper functions.
