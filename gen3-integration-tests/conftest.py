import os


def pytest_configure(config):
    # Hostname and namespace
    hostname = os.getenv("HOSTNAME")
    namespace = os.getenv("NAMESPACE")
    assert hostname is not None and namespace is not None
    # Compute namespace from hostname provided
    if not namespace:
        os.environ["NAMESPACE"] = hostname.split(".")[0]
    # Compute hostname from namespace provided
    if not hostname:
        os.environ["HOSTNAME"] = f"https://{namespace}.planx-pla.net"
    # Add scheme if hostname provided does not include it
    if hostname and "https://" not in hostname:
        os.environ["HOSTNAME"] = f"https://{hostname}"
