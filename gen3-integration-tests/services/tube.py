import pytest

from cdislogging import get_logger

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Tube(object):
    def __init__(self):
        self.BASE_URL = "https://localhost:9200"
        self.ALIAS_ENDPOINT = f"{self.BASE_URL}/_alias"
