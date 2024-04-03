import os
import pytest
import requests
import json

from dotenv import load_dotenv
from cdislogging import get_logger
from utils import TEST_DATA_PATH_OBJECT

load_dotenv()

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


""" class Nodes:
    def __init__(self, props):
        self.data = props['data']
        self.order = props['order']
        self.category = props['category']
        self.name = props['name']
        self.target = props['target']
        self.orig_props = props """


def getAllNodes():
    lines = (TEST_DATA_PATH_OBJECT / "DataImportOrderPath.txt").read_text()
    nodesDict = {}
    order = 1
    target = "project"
    for order, line in enumerate(lines.split("\n")):
        if not line:
            continue
        try:
            node_name, node_category = line.split("\t")
        except:
            print(f"Cannot parse 'DataImportOrderPath.txt' line: '{line}'")
            raise
        if node_name in ["project"]:
            continue  # project.json is not simulated
        data = open(TEST_DATA_PATH_OBJECT / "{}.json".format(node_name))
        nodesDict[node_name] = {
            "data": json.load(data)[0],
            "order": order,
            "category": node_category,
            "name": node_name,
            "target": target,
        }
        target = node_name
        order += 1
    return nodesDict


def sortNodes(nodesList):
    return dict(sorted(nodesList.items(), key=lambda item: item[1]["order"]))


def ithNodeInPath(i):
    nodesList = getAllNodes()
    for key, val in nodesList.items():
        if val["order"] == i:
            return nodesList[key]
