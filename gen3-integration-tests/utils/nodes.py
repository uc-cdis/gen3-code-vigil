import os
import pytest
import requests
import json
import random
import string

from dotenv import load_dotenv
from cdislogging import get_logger
from utils import TEST_DATA_PATH_OBJECT

load_dotenv()

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def get_all_nodes() -> dict:
    lines = (
        TEST_DATA_PATH_OBJECT / "graph_data" / "DataImportOrderPath.txt"
    ).read_text()
    nodes_dict = {}
    counter = 1
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
        data = open(TEST_DATA_PATH_OBJECT / "graph_data" / "{}.json".format(node_name))
        nodes_dict[node_name] = {
            "data": json.load(data)[0],
            "order": counter,
            "category": node_category,
            "name": node_name,
            "target": target,
        }
        target = node_name
        counter += 1
    return nodes_dict


def sort_nodes(nodes_dict: dict) -> dict:
    return dict(sorted(nodes_dict.items(), key=lambda item: item[1]["order"]))


def ith_node_in_path(i: int) -> dict:
    nodes_dict = get_all_nodes()
    for key, val in nodes_dict.items():
        if val["order"] == i:
            return nodes_dict[key]


def get_field_of_type(node: dict, field_type: object) -> str:
    for key, val in node["data"].items():
        if isinstance(val, field_type):
            return key


def get_first_node() -> dict:
    return ith_node_in_path(1)


def get_second_node() -> dict:
    return ith_node_in_path(2)


def get_last_node() -> dict:
    return ith_node_in_path(len(get_all_nodes()))


def get_path_to_file() -> dict:
    return get_path_with_file_node(get_all_nodes(), path_to_file=True)


def get_file_node() -> dict:
    return get_path_with_file_node(get_all_nodes(), file_node=True)


def get_path_with_file_node(
    all_nodes: dict, path_to_file=False, file_node=False
) -> dict:
    file_node_name = ""
    file = {}
    for key, val in all_nodes.items():
        if "_file" in val["category"]:
            file_node_name = key
    file[file_node_name] = all_nodes[file_node_name]
    del all_nodes[file_node_name]
    if path_to_file:
        return all_nodes
    if file_node:
        return file[file_node_name]


def submit_graph_and_file_metadata(
    sheepdog: object,
    file_guid=None,
    file_size=None,
    file_md5=None,
    submitter_id=None,
    consent_codes=None,
    create_new_parents=False,
    user="main_account",
    validate_node=True,
) -> dict:
    existing_file_node = get_file_node()
    metadata = existing_file_node
    if file_guid:
        metadata["data"]["object_id"] = file_guid
    if file_size:
        metadata["data"]["file_size"] = file_size
    if file_md5:
        metadata["data"]["md5sum"] = file_md5
    if submitter_id:
        metadata["data"]["submitter_id"] = submitter_id
    if consent_codes:
        if "consent_codes" not in metadata["data"].keys():
            logger.error(
                "Tried to set consent_codes but consent_codes not in dictionary. Should test be disabled?"
            )
            raise
        metadata["data"]["consent_codes"] = consent_codes
    submit_links_for_node(sheepdog, metadata, create_new_parents, user)

    if "id" in existing_file_node["data"].keys():
        sheepdog.delete_node(existing_file_node, "main_account")

    metadata = sheepdog.add_node(metadata, "main_account", validate_node)
    return metadata


def submit_links_for_node(
    sheepdog: object, record: dict, new_submitter_ids=False, user="main_account"
) -> None:
    for prop in record["data"]:
        if (
            isinstance(record["data"][prop], dict)
            and "submitter_id" in record["data"][prop].keys()
        ):
            linked_node = get_node_with_submitter_id(
                record["data"][prop]["submitter_id"]
            )
            if not linked_node:
                logger.error(
                    f"Record has a link to {record['data'][prop]['submitter_id']} but we can't find that record"
                )
                raise

            submit_links_for_node(sheepdog, linked_node, new_submitter_ids)
            if new_submitter_ids:
                res = "".join(
                    random.choices(string.ascii_lowercase + string.digits, k=5)
                )
                new_id = f"{linked_node['data']['type']}_{res}"
                linked_node["data"]["submitter_id"] = new_id
                record["data"][prop]["submitter_id"] = new_id
            sheepdog.add_node(linked_node, user, validate_node=False)


def get_node_with_submitter_id(submitter_id: str) -> dict:
    all_nodes = get_all_nodes()
    for node_name, node_details in all_nodes.items():
        if all_nodes[node_name]["data"]["submitter_id"] == submitter_id:
            return all_nodes[node_name]
