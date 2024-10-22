import subprocess


def get_test_suites():
    result = subprocess.run(
        ["poetry", "run", "pytest", "--collect-only", "-q"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    nodes = result.stdout.split("\n")[:-3]
    suites = set()
    for node in nodes:
        suites.add(node.split("::")[1])
    return sorted(suites)


# Print the list of test classes
test_suites = get_test_suites()
for suite in test_suites:
    print(suite)
