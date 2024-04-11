import os
import pytest
import requests

from cdislogging import get_logger
from gen3.auth import Gen3Auth
import requests
import json


logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Peregrine(object):
    def __init__(self):
        self.BASE_QUERY_ENDPOINT = "/api/v0/submission/graphql"

    def query(self, queryString, variableString, user):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        response = requests.post(
            url=pytest.root_url + self.BASE_QUERY_ENDPOINT,
            data=json.dumps({"query": queryString, "variables": variableString}),
            auth=auth,
        )
        return response

    def queryNodeFields(self, node, filters={}):
        fieldsString = self.fieldsToString(node["data"])
        filterString = ""
        if filters is not None and filters != {}:
            filterString = self.filterToString(filters)
            filterString = "( " + filterString + ")"

        queryToSubmit = (
            "{ " + node["name"] + " " + filterString + " {" + fieldsString + " } }"
        )
        return self.query(queryToSubmit, {}, "main_account")

    def fieldsToString(self, data):
        primitive_types = [int, float, bool, str]
        fieldsString = ""
        for key, val in data.items():
            if type(val) in primitive_types:
                fieldsString += "\n{}".format(key)
        return fieldsString

    def filterToString(self, filters):
        filterString = []
        for key, val in filters.items():
            if isinstance(val, str):
                filterString.append('{}: "{}"'.format(key, val))
        return ", ".join(filterString)
