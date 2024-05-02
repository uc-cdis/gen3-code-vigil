import json
import os
import pytest
import requests

from cdislogging import get_logger

from gen3.auth import Gen3Auth

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Peregrine(object):
    def __init__(self):
        self.BASE_QUERY_ENDPOINT = "/api/v0/submission/graphql"

    def query(self, query_string: str, variable_string: str, user: str) -> dict:
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        response = requests.post(
            url=pytest.root_url + self.BASE_QUERY_ENDPOINT,
            data=json.dumps({"query": query_string, "variables": variable_string}),
            auth=auth,
        )
        return response

    def query_to_submit(self, node: dict, filters={}) -> str:
        fields_string = self.fields_to_string(node.props)
        filter_string = ""
        if filters is not None and filters != {}:
            filter_string = self.filter_to_string(filters)
            filter_string = "( " + filter_string + ")"

        query_for_submission = (
            "{ " + node.node_name + " " + filter_string + " {" + fields_string + " } }"
        )
        return query_for_submission

    def fields_to_string(self, data: dict) -> str:
        primitive_types = [int, float, bool, str]
        fields_string = ""
        for key, val in data.items():
            if type(val) in primitive_types:
                fields_string += "\n{}".format(key)
        return fields_string

    def filter_to_string(self, filters: dict) -> str:
        filter_string = []
        for key, val in filters.items():
            if isinstance(val, str):
                filter_string.append('{}: "{}"'.format(key, val))
        return ", ".join(filter_string)

    def query_count(self, type_count: str) -> dict:
        query_to_submit = "{" + type_count + "}"
        return self.query(query_to_submit, {}, "main_account")

    def query_with_path_to(self, from_node: dict, to_node: dict) -> str:
        query_to_submit = (
            "query Test { "
            + from_node.node_name
            + ' (order_by_desc: "created_datetime",with_path_to: { type: "'
            + to_node.node_name
            + '", submitter_id: "'
            + to_node.props["submitter_id"]
            + '"} ) { submitter_id } }'
        )
        return query_to_submit

    def see_json_core_metadata(self, file, metadata):
        metadata = metadata.json()
        assert (
            file.props["file_name"] == metadata["file_name"]
        ), f"file_name not matched/found.\n{file}\n{metadata}"
        assert (
            file.indexd_guid == metadata["object_id"]
        ), f"object_id not matched/found.\n{file}\n{metadata}"
        assert (
            file.props["type"] == metadata["type"]
        ), f"type not matched/found.\n{file}\n{metadata}"
        assert (
            file.props["data_format"] == metadata["data_format"]
        ), f"data_format not matched/found.\n{file}\n{metadata}"
