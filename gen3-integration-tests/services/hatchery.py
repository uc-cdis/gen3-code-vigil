import pytest


class Hatchery(object):
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}/explorer"
