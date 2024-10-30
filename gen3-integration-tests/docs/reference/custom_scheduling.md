Test suites run in parallel by default using xdist. In some scenarios we might want to group tests in different suites together and run by the same worker.

For example, we want the same worker to run all tests that launch a workspace since we can launch only one workspace at a time in Gen3. Running them in parallel could break some of them if different tests are trying to run different operations on the same workspace.

We implemented this special logic [here](../../conftest.py#37) that overrides the default behavior of the `--loadscope` flag by grouping all tests having the marker `workspace`.
