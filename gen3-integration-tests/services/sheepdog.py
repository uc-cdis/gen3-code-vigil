import os
import pytest
import requests

from cdislogging import get_logger
from gen3.auth import Gen3Auth
from utils import TEST_DATA_PATH_OBJECT
from utils import nodes
from services.peregrine import Peregrine
import requests
import json


logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class Sheepdog(object):
    def __init__(self, program, project):
        self.BASE_ADD_ENDPOINT = "/api/v0/submission"
        self.program = program
        self.project = project

    def get_did_from_file_id(self, file_node: dict, auth: Gen3Auth) -> str:
        if not file_node["data"]["id"]:
            logger.error(
                "Parameter id is missing from node. Node details: {}".format(file_node)
            )
            raise
        response = requests.get(
            url=pytest.root_url
            + self.BASE_ADD_ENDPOINT
            + "/{}/{}/export?ids={}&format=json".format(
                self.program, self.project, file_node["data"]["id"]
            ),
            auth=auth,
        )
        return response.json()[0]["object_id"]

    def add_node(
        self,
        node: dict,
        user: str,
        validate_node=True,
        validate_node_update=False,
        invalid_property=False,
    ) -> dict:
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        response = requests.put(
            url=pytest.root_url
            + self.BASE_ADD_ENDPOINT
            + f"/{self.program}/{self.project}",
            data=json.dumps(node["data"]),
            auth=auth,
        )
        data = response.json()
        node["addRes"] = data
        node["data"]["id"] = data["entities"][0]["id"]

        if (
            "_file" in node["category"]
            and not invalid_property
            and node["addRes"]["code"] in [200, 201]
        ):
            node["did"] = self.get_did_from_file_id(node, auth)

        # Validate node was created
        if validate_node:
            if validate_node_update:
                property_to_check = data["updated_entity_count"]
            else:
                property_to_check = data["created_entity_count"]
            if property_to_check != 1:
                logger.error("Node wasn't created. Node details : {}".format(node))
                raise
        return node

    def add_nodes(self, nodes_dict: dict, user: str) -> dict:
        nodes_mapping = {}
        sortedNodes = nodes.sort_nodes(nodes_dict).items()
        for key, val in sortedNodes:
            logger.info("Adding node for {}".format(key))
            node = self.add_node(val, user)
            nodes_mapping[key] = node
        return nodes_mapping

    def update_node(
        self,
        node: dict,
        user: str,
        validate_node=True,
        validate_node_update=True,
        invalid_property=False,
    ) -> dict:
        return self.add_node(
            node, user, validate_node, validate_node_update, invalid_property
        )

    def delete_node(self, node: dict, user: str, validate_node=True) -> None:
        id = node["data"]["id"]
        if not id:
            logger.error("Cannot delete node because node.data.id is missing")
            raise
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        response = requests.delete(
            url=pytest.root_url
            + self.BASE_ADD_ENDPOINT
            + "/{}/{}/entities/{}".format(self.program, self.project, id),
            auth=auth,
        )
        data = response.json()

        # Validate node was deleted
        if validate_node:
            if data["deleted_entity_count"] != 1:
                logger.error(
                    "Node wasn't deleted. Node delete response : {}".format(data)
                )
                raise

    def delete_nodes(self, nodes_dict: dict, user: str) -> None:
        for key, val in dict(
            sorted(nodes_dict.items(), key=lambda item: item[1]["order"], reverse=True)
        ).items():
            logger.info("Deleting node for {}".format(key))
            self.delete_node(val, user)

    def delete_all_nodes(self) -> None:
        peregrine = Peregrine()
        topNode = "project"
        queryToSubmit = (
            "{"
            + topNode
            + "(first: 0) {code programs {  name    }    _links {  id  submitter_id    }    }}"
        )
        response = peregrine.query(queryToSubmit, {}, "main_account")
        data = response.json()["data"]
        while len(data[topNode]) > 0:
            linkedType = data[topNode].pop()
            project = linkedType["code"]
            program = linkedType["programs"][0]["name"]
            while len(linkedType["_links"]) > 0:
                linkedTypeInstance = linkedType["_links"].pop()
                self.delete_by_id_recursively(
                    linkedTypeInstance["id"], project, program, "main_account"
                )

    def delete_by_id_recursively(
        self, id: str, project: str, program: str, user: str
    ) -> None:
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        # Endpoint for deleting the node using id
        BASE_DELETE_ENDPOINT = "/api/v0/submission/{}/{}/entities/{}".format(
            program, project, id
        )
        response = requests.delete(
            url=pytest.root_url + BASE_DELETE_ENDPOINT, auth=auth
        )
        data = response.json()
        if "dependent_ids" not in data:
            logger.error(
                "Error deleting by ID recursively. Result missing 'dependent_ids' property: {}".format(
                    data
                )
            )
            raise

        # Deleted successfully
        if data["code"] == 200 and data["dependent_ids"] == "":
            return

        # Need to delete depenedent(s)
        if data["code"] != 200 and data["dependent_ids"] != "":
            dependents = data["dependent_ids"].split(",")
            self.delete_by_id_recursively(
                dependents[0], project, program, "main_account"
            )
            self.delete_by_id_recursively(id, project, program, "main_account")
