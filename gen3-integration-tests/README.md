# Setup

Create a .env file containing in `gen3-code-vigil/gen3-integration-tests` with the values:

```
JENKINS_USERNAME=PlanXCyborg
JENKINS_PASSWORD=<Jenkins API Token>
```
At this point in time we use Jenkins hosted in the same host as the test environment to perform administration tasks. The JENKINS_* variables are not needed once this mechanism changes.

Save API key for the environment in `~/.gen3`

# Running Tests

Switch `gen3-code-vigil/gen3-integration-tests` to run the command:
```
HOSTNAME="jenkins-brain.planx-pla.net" poetry run pytest --html=output/report.html --self-contained-html -n auto
```
The kubernetes namespace is required for Gen3 admin tasks. It is assumed to be the first part of the hostname (`jenkins-brain` in the example above).
If it is different specify it explicitly, like
```
HOSTNAME="jenkins-brain.planx-pla.net" NAMESPACE="something_else" poetry run pytest --html=output/report.html --self-contained-html -n auto
```

`-n auto` comes from [python-xdist](https://pypi.org/project/pytest-xdist/). To use this feature it is imperative that the tests are designed to be independent and idempotent.

Markers and `-m` flag can be used to specify what tests should or should not run. For example, `-m wip` selects only tests with marker `wip` and `-m not wip` skips tests with marker `wip`. Read more about marking tests [here](https://docs.pytest.org/en/7.1.x/example/markers.html)
