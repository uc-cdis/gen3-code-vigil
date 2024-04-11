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
    def __init__(self):
        self.BASE_ADD_ENDPOINT = "/api/v0/submission"

    def addNode(self, node, user, validate_node=True):
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        response = requests.put(
            url=pytest.root_url + self.BASE_ADD_ENDPOINT + "/jnkns/jenkins",
            data=json.dumps(node["data"]),
            auth=auth,
        )
        data = response.json()
        node["addRes"] = data
        node["data"]["id"] = data["entities"][0]["id"]

        # Validate node was created
        if validate_node:
            if data["created_entity_count"] != 1:
                logger.error("Node wasn't created. Node details : {}".format(node))
                raise
        return node

    def deleteNode(self, node, user, validate_node=True):
        id = node["data"]["id"]
        if not id:
            logger.error("Cannot delete node because node.data.id is missing")
            raise
        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        response = requests.delete(
            url=pytest.root_url
            + self.BASE_ADD_ENDPOINT
            + "/jnkns/jenkins/entities/{}".format(id),
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
        return

    def deleteAllNodes(self):
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
                self.deleteByIdRecursively(
                    linkedTypeInstance["id"], project, program, "main_account"
                )

    def deleteByIdRecursively(self, id, project, program, user):
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
            self.deleteByIdRecursively(dependents[0], project, program, "main_account")
            self.deleteByIdRecursively(id, project, program, "main_account")
