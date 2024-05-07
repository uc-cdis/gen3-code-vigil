import copy
import json
import os
import uuid
import pytest
import random
import string

from cdislogging import get_logger
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission
import requests

from utils import TEST_DATA_PATH_OBJECT


logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class GraphRecord:
    def __init__(
        self, node_name: str, category: str, submission_order: int, props: dict
    ) -> None:
        """
        node_name: id of the node in the dictionary (example: "case")
        category: category of the node in the dictionary (example: "administrative")
        submission_order: index of this record in the submission order (example: 2)
        props: record as it should be submitted to sheepdog
        unique_id: unique "id" property returned by sheepdog when submitting a record
        indexd_guid: for *_file nodes, the guid of the referenced file in indexd
        """
        self.node_name = node_name
        self.category = category
        self.submission_order = submission_order
        self.props = props
        self.unique_id = None
        self.indexd_guid = None

    '''def __str__(self) -> str:
        return f"GraphRecord '{self.node_name}': {self.props}"'''


class GraphDataTools:
    """
    Tools to interact with graph data (Sheepdog service for submissions, Peregrine service for queries).
    """

    def __init__(
        self, auth: Gen3Auth, program_name: str = "jnkns", project_code: str = "jenkins"
    ) -> None:
        self.sdk = Gen3Submission(auth_provider=auth)
        self.auth = auth
        self.program_name = program_name
        self.project_code = project_code
        self.project_id = f"{self.program_name}-{self.project_code}"
        self.test_data_path = TEST_DATA_PATH_OBJECT / "graph_data"
        self.submission_order = []  # node names in the order they should be submitted
        # records as generated by data-simulator - { node name: GraphRecord }
        self.test_records = {}
        self._load_test_records()
        self.BASE_ADD_ENDPOINT = "/api/v0/submission"

    def create_program_and_project(self) -> None:
        """
        Creates a program record and a project record. Uses the `program_name` and `project_code`
        set during the initialization of the `GraphDataTools` instance.
        """
        logger.info(
            f"Creating program '{self.program_name}' and project '{self.project_code}'"
        )
        program_record = {
            "type": "program",
            "name": self.program_name,
            "dbgap_accession_number": self.program_name,
        }
        self.sdk.create_program(program_record)

        project_record = {
            "type": "project",
            "code": self.project_code,
            "name": self.project_code,
            "dbgap_accession_number": self.project_code,
        }
        self.sdk.create_project(self.program_name, project_record)

    def delete_all_records_in_test_project(self) -> None:
        """
        Clean up before starting the test suite (useful when running tests locally)
        """
        for node_name in reversed(self.submission_order):
            query = f'query {{ {node_name} (project_id: "{self.project_id}", first: 0) {{ id }} }}'
            result = self.graphql_query(query).get("data", {}).get(node_name, [])
            for record in result:
                logger.info(
                    f"Pre-test clean up: deleting '{node_name}' record '{record['id']}'"
                )
                self._delete_record(record["id"])

    def _load_test_records(self) -> None:
        """
        Load into `self.test_records` all the test records as generated and saved at
        `test_data/graph_data` by `generate_graph_data()`.
        Load `DataImportOrderPath.txt` into `self.submission_order`.
        """
        lines = (self.test_data_path / "DataImportOrderPath.txt").read_text()
        for order, line in enumerate(lines.split("\n")):
            if not line:
                continue
            try:
                node_name, node_category = line.split("\t")
            except:
                print(f"Cannot parse 'DataImportOrderPath.txt' line: '{line}'")
                raise
            if node_name in ["program", "project"]:
                continue  # program and project are created separately
            self.submission_order.append(node_name)
            file_path = self.test_data_path / f"{node_name}.json"
            try:
                props = json.loads(file_path.read_text())
            except Exception:
                logger.error(f"Unable to load file '{node_name}.json'")
                raise
            if type(props) == list:
                if len(props) == 1:
                    props = props[0]
                else:
                    raise Exception(
                        f"Expected 1 record per test record file, but found {len(props)} in {node_name}.json"
                    )
            self.test_records[node_name] = GraphRecord(
                node_name, node_category, order, props
            )

    def _submit_record(
        self, record: GraphRecord, expected_status_code: int = 200
    ) -> dict:
        """
        Submit a record to the graph data database.

        Args:
            record: record to submit
            expected_status_code: 200 by default, allows us to expect a failure in tests
        """
        try:
            result = self.sdk.submit_record(
                self.program_name, self.project_code, record.props
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code != expected_status_code:
                logger.error(f"Error while submitting record: {e.response.text}")
                raise
        record.unique_id = result["entities"][0]["id"]
        return result

    def submit_all_test_records(self) -> None:
        """
        Following the order set by `self.submission_order`, submit all the records in `self.test_records`,
        in the right order.
        """
        for node_name in self.submission_order:
            self._submit_record(self.test_records[node_name])

    def submit_new_record(self, node_name: str) -> GraphRecord:
        """
        Starting from a generated test data record, submit a new record with a
        new unique submitter_id.

        Args:
            node_name: the node type of the new record.
        """
        record = copy.deepcopy(self.test_records[node_name])
        record.props["submitter_id"] = f"{node_name}_{str(uuid.uuid4())[:8]}"
        self._submit_record(record)
        return record

    def _delete_record(
        self, unique_id: str, expected_status_code: int = 200
    ) -> requests.Response:
        """
        Delete one record from the graph data database.

        Args:
            unique_id: the record's ID in the DB
            expected_status_code: 200 by default, allows us to expect a failure in tests
        """
        if not unique_id:
            raise Exception("Unable to delete record that has no unique_id")
        return self.delete_records([unique_id], expected_status_code)

    def delete_records(
        self, unique_ids: [str], expected_status_code: int = 200
    ) -> requests.Response:
        """
        Delete a list of records from the graph data database.

        Args:
            unique_ids: list of the records' IDs in the DB
            expected_status_code: 200 by default, allows us to expect a failure in tests
        """
        try:
            result = self.sdk.delete_records(
                self.program_name, self.project_code, unique_ids
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code != expected_status_code:
                logger.error(f"Error while deleting record: {e.response.text}")
                raise
        return result

    def delete_all_test_records(self) -> None:
        """
        Following the order set by `self.submission_order`, delete all the records in `self.test_records`,
        in the right order.
        """
        to_delete = []
        for node_name in reversed(self.submission_order):
            record = self.test_records[node_name]
            if not record.unique_id:
                continue  # this record was never submitted
            to_delete.append(record.unique_id)
        self.delete_records(to_delete)

    def delete_nodes(self, expected_status_code: int = 200):
        try:
            result = self.sdk.delete_nodes(
                self.program_name, self.project_code, self.submission_order[::-1]
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code != expected_status_code:
                logger.error(f"Error while deleting nodes: {e.response.text}")
                raise
        return result

    def graphql_query(self, query_text: str, variables: dict = None) -> dict:
        """
        Query the graph data database through a GraphQL query.

        Args:
            query_text: body of the GraphQL query
            variables: variables of the GraphQL query
        """
        logger.info(f"Graph data query: '{query_text}'. Variables: '{variables}'")
        return self.sdk.query(query_text, variables)

    def query_node_count(self, node_name: str) -> dict:
        """
        Query the graph data database for the number of records in a node.

        Args:
            node_name: the name of the node for which to query the count
        """
        query = f'{{ _{node_name}_count (project_id: "{self.project_id}") }}'
        return self.graphql_query(query)

    def submit_single_record(self, record: GraphRecord):
        """
        Submit a single record
        """
        return self._submit_record(record=record)

    def get_ith_record(self, position: int):
        """
        Get the record for ith based node position.

        Args:
            i: position - python based position, starts from 0 and ends with -1
        """
        return self.test_records[self.submission_order[position]]

    def get_path_with_file_node(self, path_to_file=False, file_node=False):
        """
        Get all nodes except node with _file category or get node with _file category

        Args:
            path_to_file: returns all nodes except for node with _file category
            file_node : returns the node with _file category
        """
        all_nodes = copy.deepcopy(self.test_records)
        file_node_name = ""
        for node_name in self.submission_order:
            if "_file" in all_nodes[node_name].category:
                file_node_name = node_name
        file_node_item = all_nodes[file_node_name]
        del all_nodes[file_node_name]
        if path_to_file:
            return all_nodes
        if file_node:
            return file_node_item

    def get_field_of_type(self, node: dict, field_type: object) -> str:
        """
        Gets the field of desired data type

        Args:
            field_type: python object like str, int, dict, etc.
        """
        for key, val in node.props.items():
            if isinstance(val, field_type):
                return key

    def get_did_from_file_id(self, guid: str) -> str:
        """
        Returns the did/indexd_guid value for file node
        Args:
            guid: node's entities based id
        """
        response = requests.get(
            url=pytest.root_url
            + self.BASE_ADD_ENDPOINT
            + "/{}/{}/export?ids={}&format=json".format(
                self.program_name, self.project_code, guid
            ),
            auth=self.auth,
        )
        return response.json()[0]["object_id"]

    def submit_graph_and_file_metadata(
        self,
        file_guid=None,
        file_size=None,
        file_md5=None,
        submitter_id=None,
        consent_codes=None,
        create_new_parents=False,
        user="main_account",
    ) -> dict:
        """
        Submits the graph and file metadata
        Args:
            file_guid: File GUID (optional)
            file_size: File Size (optional)
            file_md5: File MD5 (optional)
            submitter_id: Submitter Id (optional)
            consent_codes: Consent Codes (optional)
            create_new_parents: Creates new parents incase of existing nodes. Boolean value.
            user: user having permission to submit nodes
        """
        existing_file_node = self.get_path_with_file_node(file_node=True)
        metadata = existing_file_node
        if file_guid:
            metadata.props["object_id"] = file_guid
        if file_size:
            metadata.props["file_size"] = file_size
        if file_md5:
            metadata.props["md5sum"] = file_md5
        if submitter_id:
            metadata.props["submitter_id"] = submitter_id
        if consent_codes:
            if "consent_codes" not in metadata.props.keys():
                logger.info("Consent Codes not available in dictionary")
                pytest.skip("Consent Codes not available in dictionary")
            metadata.props["consent_codes"] += consent_codes
        self.submit_links_for_node(metadata, create_new_parents, user)

        if "id" in existing_file_node.props.keys():
            self._delete_record(unique_id=existing_file_node.unique_id)

        self._submit_record(record=metadata)
        return metadata

    def submit_links_for_node(
        self, record: dict, new_submitter_ids=False, user="main_account"
    ) -> None:
        for prop in record.props:
            if (
                isinstance(record.props[prop], dict)
                and "submitter_id" in record.props[prop].keys()
            ):
                linked_node = self.get_node_with_submitter_id(
                    record.props[prop]["submitter_id"]
                )
                if not linked_node:
                    logger.error(
                        f"Record has a link to {record.props[prop]['submitter_id']} but we can't find that record"
                    )
                    raise

                self.submit_links_for_node(linked_node, new_submitter_ids)
                if new_submitter_ids:
                    res = "".join(
                        random.choices(string.ascii_lowercase + string.digits, k=5)
                    )
                    new_id = f"{linked_node.props['type']}_{res}"
                    linked_node.props["submitter_id"] = new_id
                    record.props[prop]["submitter_id"] = new_id
                self._submit_record(record=linked_node)

    def get_node_with_submitter_id(self, submitter_id: str) -> dict:
        all_nodes = self.test_records
        for node_name, node_details in all_nodes.items():
            if node_details.props["submitter_id"] == submitter_id:
                return all_nodes[node_name]

    def get_dependent_node(self) -> GraphRecord:
        """
        Gets the first available child node
        """
        for key, val in self.test_records.items():
            for prop in val.props:
                if (
                    isinstance(val.props[prop], dict)
                    and "submitter_id" in val.props[prop].keys()
                ):
                    return val
