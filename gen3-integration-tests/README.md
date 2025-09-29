# Overview
This is the repository for managing Gen3 integration tests. The code is written in Python, and the following tools/frameworks are used:

- **`poetry`** (package management [docs](https://python-poetry.org/docs/))
- **`pytest`** (testing framework [docs](https://docs.pytest.org/en/stable/))
- **`requests`** (tool for making HTTP requests [docs](https://docs.python-requests.org/en/master/))
- **`playwright`** (tool for automating web applications [docs](https://playwright.dev/python/docs/intro))
- **`gen3sdk-python`** (SDK for handling common Gen3 tasks [docs](https://github.com/uc-cdis/gen3sdk-python))
- **`xdist`** (parallel test execution [docs](https://pytest-xdist.readthedocs.io/en/stable/))
- **`allure`** (tool for visualizing test results [docs](https://allurereport.org/docs/pytest/))

# Running tests

## Setup

### Set up prerequisites

#### Checkout and switch directory
Checkout this repo and switch to `gen3-integration-tests` directory. This is the root directory for integration tests.

#### Create `~/.gen3` directory
The integration tests look for API keys in this location. Make sure you created this directory.

#### Create `.env` file
Switch to `gen3-integration-tests` directory and create a `.env` file. The code is designed to fetch environment variables set in this file.

#### Create output and install dependencies
*The output directory is used to store the markdown report that is also generated along with the allure report.*

Switch to `gen3-code-vigil/gen3-integration-tests` and run the commands:
```
mkdir output
poetry install
```

### Set up test users
The code supports running test steps as different users. This [code](conftest.py#L103-L116) can provide insights into the set up process.

The test users required to run the tests are listed [here](test_data/test_setup/users.csv).

The API keys for these users must be saved to `~/.gen3` directory before running tests.[here](docs/howto/generate_api_keys_for_test_users/)

### Set up test user permissions
User permissions required for the tests to pass are documented [here](test_data/test_setup/user.yaml). The tests attempt to run usersync before starting, so if usersync is correctly set up with this configuration there is nothing more to do. If that is not the case please make sure to run usersync or useryaml with this configuration before running the tests.

### Set up test data
#### Guppy
We run guppy tests with fixed ES data to enable data validation consistently. Before running guppy tests we must ensure the indices are created with the required data. We can use one of the setup scripts located [here](test_data/test_setup/guppy_es) depending on the type of Gen3 instance being tested.

## Run tests and review results
Read these [docs](docs/howto/run_tests/) for specific information on how to run tests.

The report can be viewed by running `allure serve allure-results`

`-n auto` comes from [python-xdist](https://pypi.org/project/pytest-xdist/). `auto` distributes tests across all available CPUs. We can set to to a smaller value to use only some of the cores.

Test classes / suites run in parallel using the `--dist loadscope`. We implemented custom scheduling for grouping tests across test suites which is explained [here](docs/reference/custom_scheduling.md)

Markers and `-m` flag can be used to specify what tests should or should not run. For example, `-m wip` selects only tests with marker `wip` and `-m not wip` skips tests with marker `wip`.

`-k` flag can be used to run specific test suites (test suite name is the class name), e.g.
- `-k TestHomePage` runs only the test_homepage.py
- `-k "TestHomePage or TestETL"` runs test_homepage.py

Read more about marking tests [here](https://docs.pytest.org/en/7.1.x/example/markers.html)

# Writing tests

## Design principles
- The test suites must be independent and idempotent. This is essential since we run test classes in parallel by using xdist (loadscope).
- All tests should be able to run anywhere (locally / CI) without changing test code.
- Debugging must be done locally, not in CI pipeline.
- Documentation is essential. Code is incomplete without it.
- Avoid hard waits. Test should wait for application state, not otherwise.
- Tag tests appropriately using markers. Ensure that the markers are added [here](./pyproject.toml#44)
- Add test steps as docstrings in the test for understanding the purpose of the test easily.
- Mark in-progress tests with marker `wip` to prevent CI pipeline from breaking when incomplete test code is pushed to repo.
- Ensure that privileged information is not logged since the tests run in Github Actions and the logs are public.

## Code structure
The test code is organized into several directories for ease of maintenance:

- **`tests`**: Contains tests written in pytest
- **`test_data`**: Contains test data needed for integration tests.
- **`pages`**: Contains endpoint definitions, locators, and methods specific to each page in the portal, with a separate module for each page.
- **`services`**: Contains endpoints and methods specific to each service, with a separate module for each service.
- **`utils`**: Provides utility and helper functions used across tests.
- **`scripts`**: Includes standalone helper scripts used for setting up the test environment.

[conftest.py](./conftest.py) controls the test flow.

The integration tests perform Gen3 operations and admin tasks, e.g., etl, metadata-aggregate-sync as part of the test flow. The code for handling these is at [utils/gen3_admin_tasks](utils/gen3_admin_tasks.py). Read this [doc](docs/howto/run_admin_tasks/) for more information.

Code used for running integration tests in CI at CTDS is at `gen3-code-vigil/gen3-integration-tests/gen3_ci`.
- **`scripts`** directory contains python scripts used in the github actions workflow.

Tests are organized into test suites using classes as explained [here](https://docs.pytest.org/en/stable/getting-started.html#group-multiple-tests-in-a-class).
