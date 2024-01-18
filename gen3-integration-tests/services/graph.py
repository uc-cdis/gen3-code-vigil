import copy
import json
import os
import uuid

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
        # self.category = category  # not used yet
        self.submission_order = submission_order
        self.props = props
        self.unique_id = None
        # self.indexd_guid = None  # not used yet

    def __str__(self) -> str:
        return f"GraphRecord '{self.node_name}': {self.props}"


class GraphDataTools:
    """
    Tools to interact with graph data (Sheepdog service for submissions, Peregrine service for queries).
    """

    def __init__(
        self, auth: Gen3Auth, program_name: str = "jnkns", project_code: str = "jenkins"
    ) -> None:
        self.sdk = Gen3Submission(auth_provider=auth)
        self.program_name = program_name
        self.project_code = project_code
        self.project_id = f"{self.program_name}-{self.project_code}"
        self.test_data_path = TEST_DATA_PATH_OBJECT / "graph_data"
        self.submission_order = []  # node names in the order they should be submitted
        # records as generated by data-simulator - { node name: GraphRecord }
        self.test_records = {}
        self._load_test_records()

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
            props = json.loads((self.test_data_path / f"{node_name}.json").read_text())
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
