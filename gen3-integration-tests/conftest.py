import os


def pytest_configure(config):
    hostname = os.getenv("HOSTNAME")
    namespace = os.getenv("NAMESPACE")
    if not namespace:
        os.environ["NAMESPACE"] = hostname.split(".")[0]
