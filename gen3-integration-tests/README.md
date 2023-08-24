# Setup

Create a .env file containing in `gen3-code-vigil/gen3-integration-tests` with the values:

```
JENKINS_USERNAME=PlanXCyborg
JENKINS_PASSWORD=*****
```

Set the values in the pyproject.toml's `tool.pytest.ini_options` block to point to the right test environment.

Save API key for the environment in `~/.gen3`

Switch `gen3-code-vigil/gen3-integration-tests` to Run the command:
```
poetry run pytest
```
