# import json
import os
import pytest

from cdislogging import get_logger
from gen3.submission import Gen3Submission


logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Peregrine:
    def __init__(self):
        # TODO gen3auth global created in conftest and passed to other classes. Can be None.
        from gen3.auth import Gen3Auth

        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        self.sdk = Gen3Submission(auth_provider=auth)

    def query(self, query_text, variables=None):
        logger.info(f"Peregrine query: '{query_text}'. Variables: '{variables}'")
        return self.sdk.query(query_text, variables)

    def query_node_count(self, node_name):
        query = f"{{ _{node_name}_count }}"
        return self.query(query)
