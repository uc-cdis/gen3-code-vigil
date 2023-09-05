# Setup

Create a .env file containing in `gen3-code-vigil/gen3-integration-tests` with the values:

```
JENKINS_USERNAME=PlanXCyborg
JENKINS_PASSWORD=<Jenkins API Token>
```
At this point in time we use Jenkins hosted in the same host as the test environment to perform administration tasks. The JENKINS_* variables are not needed.

Set the values in the pyproject.toml's `tool.pytest.ini_options` block to point to the right test environment.

Save API key for the environment in `~/.gen3`

Switch `gen3-code-vigil/gen3-integration-tests` to Run the command:
```
HOSTNAME="jenkins-brain.planx-pla.net" poetry run pytest --html=report.html --self-contained-html -n auto
```
The kubernetes namespace is required for Gen3 admin tasks. It is assumed to be the first part of the hostname (`jenkins-brain` in the example above).
If it is different specify it explicitly, like
```
HOSTNAME="jenkins-brain.planx-pla.net" NAMESPACE="something_else" poetry run pytest --html=report.html --self-contained-html -n auto
```
