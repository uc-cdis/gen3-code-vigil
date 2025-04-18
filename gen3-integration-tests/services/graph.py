import copy
import json
import os
import random
import string
import uuid

import psutil
import pytest
import requests
from datasimulator.main import (
    initialize_graph,
    run_simulation,
    run_submission_order_generation,
)
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission
from packaging.version import Version
from utils import TEST_DATA_PATH_OBJECT, logger
from utils.misc import retry


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

    def __str__(self) -> str:
        return f"GraphRecord '{self.node_name}': {self.props}"


class GraphDataTools:
    """
    Tools to interact with graph data (Sheepdog service for submissions, Peregrine service for queries).
    """

    def __init__(
        self, auth: Gen3Auth, program_name: str = "jnkns", project_code: str = "jenkins"
    ) -> None:
        self.program_name = program_name
        self.project_code = project_code
        self.project_id = f"{self.program_name}-{self.project_code}"
        self.test_data_path = (
            TEST_DATA_PATH_OBJECT / "graph_data" / f"{self.project_id}"
        )
        self._generate_graph_data()
        self.sdk = Gen3Submission(auth_provider=auth)
        self.BASE_URL = "/api/v0/submission/"
        self.GRAPHQL_VERSION_ENDPOINT = "/api/search/_version"
        self.auth = auth
        self.submission_order = []  # node names in the order they should be submitted
        # records as generated by data-simulator - { node name: GraphRecord }
        self.test_records = {}
        self.linked_test_submitter_ids = {}
        self._create_program()
        self._create_project()
        self._load_test_records()

    def _generate_graph_data(self) -> None:
        """
        Call data-simulator functions to generate graph data for each node in the dictionary and to generate
        the submission order.
        """
        try:
            manifest = json.loads(
                (TEST_DATA_PATH_OBJECT / "configuration/manifest.json").read_text()
            )
        except FileNotFoundError:
            logger.error(
                "manifest.json not found. It should have been fetched by `get_configuration_files`..."
            )
            raise

        dictionary_url = manifest.get("global", {}).get("dictionary_url")
        assert dictionary_url, "No dictionary URL in manifest.json"

        data_path = self.test_data_path
        data_path.mkdir(parents=True, exist_ok=True)

        max_samples = 1  # the submission functions in services/graph.py assume there is only 1 record per node
        required_only = False

        graph = initialize_graph(
            dictionary_url=dictionary_url,
            program=self.program_name,
            project=self.project_code,
            consent_codes=False,
        )
        run_simulation(
            graph=graph,
            data_path=data_path,
            max_samples=max_samples,
            node_num_instances_file=None,
            random=True,
            required_only=required_only,
            skip=True,
        )
        # NOTE: not using a "leaf node" like in old gen3-qa tests... just generating everything.
        # Submission takes more time, but data is more representative of real data.
        run_submission_order_generation(
            graph=graph, data_path=data_path, node_name=None
        )

        logger.info("Done generating data:")
        for f_path in sorted(os.listdir(data_path)):
            with open(data_path / f_path, "r") as f:
                logger.info(f"{f_path}:\n{f.read()}")

    @retry(times=3, delay=5, exceptions=(requests.exceptions.HTTPError,))
    def _create_program(self) -> None:
        """
        Creates a program record. Uses the `program_name` set during the initialization
        of the `GraphDataTools` instance.

        """
        # Check if program exists or not
        if (
            f"/v0/submission/{self.program_name}"
            not in self.sdk.get_programs()["links"]
        ):
            logger.info(
                f"Creating program '{self.program_name}' and project '{self.project_code}'"
            )
            program_record = {
                "type": "program",
                "name": self.program_name,
                "dbgap_accession_number": self.program_name,
            }
            self.sdk.create_program(program_record)

    @retry(times=3, delay=5, exceptions=(requests.exceptions.HTTPError,))
    def _create_project(self) -> None:
        """
        Creates a project record. Uses the `program_name` and `project_code`
        set during the initialization of the `GraphDataTools` instance.
        """
        # Check if project exists or not
        if (
            f"/v0/submission/{self.program_name}/{self.project_code}"
            not in self.sdk.get_projects(self.program_name)["links"]
        ):
            project_record = {
                "type": "project",
                "code": self.project_code,
                "name": self.project_code,
                "dbgap_accession_number": self.project_code,
            }
            self.sdk.create_project(self.program_name, project_record)

    @retry(times=3, delay=10, exceptions=(AssertionError))
    def _load_test_records(self) -> None:
        """
        Load into `self.test_records` all the test records as generated and saved at
        `test_data/graph_data` by `generate_graph_data()`.
        Load `DataImportOrderPath.txt` into `self.submission_order`.
        """
        self.submission_order = []
        self.test_records = {}
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
                with file_path.open() as fp:
                    props = json.load(fp)
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

    def submit_record(
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
        logger.info(f"submission order: {self.submission_order}")
        for node_name in self.submission_order:
            logger.info(f"Submitting record for {node_name}")
            logger.info(self.test_records[node_name])
            self.submit_record(self.test_records[node_name])

    def submit_new_record(self, node_name: str) -> GraphRecord:
        """
        Starting from a generated test data record, submit a new record with a
        new unique submitter_id.

        Args:
            node_name: the node type of the new record.
        """
        record = copy.deepcopy(self.test_records[node_name])
        record.props["submitter_id"] = f"{node_name}_{str(uuid.uuid4())[:8]}"
        self.submit_record(record)
        return record

    def delete_record(
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

    def delete_all_records(self):
        """
        Delete a list of nodes from the graph data database.
        """
        try:
            self.sdk.delete_nodes(
                self.program_name, self.project_code, self.submission_order[::-1]
            )
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error while deleting nodes: {e.response.text}")
            raise

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

    def get_file_record(self):
        """
        Returns a record which has category ending with _file
        """
        for node_name in self.submission_order:
            if self.test_records[node_name].category.endswith("_file"):
                return copy.deepcopy(self.test_records[node_name])

    def get_indexd_id_from_graph_id(self, unique_id: str) -> str:
        """
        Returns the did/indexd_guid value for file node
        Args:
            unique_id: sheepdog record id
        """
        response = requests.get(
            url=pytest.root_url
            + self.BASE_URL
            + "{}/{}/export?ids={}&format=json".format(
                self.program_name, self.project_code, unique_id
            ),
            auth=self.auth,
        )
        return response.json()[0]["object_id"]

    # TODO: Remove if not used after migration is complete
    '''def submit_graph_and_file_metadata(
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
        existing_file_node = self.get_file_node()
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
            metadata.props["consent_codes"] += consent_codes
        self.submit_links_for_record(metadata, create_new_parents, user)

        if "id" in existing_file_node.props.keys():
            self.delete_record(unique_id=existing_file_node.unique_id)

        self.submit_record(record=metadata)
        return metadata'''

    def regenerate_graph_data(self):
        logger.info("Regenerating the graph data")
        self._generate_graph_data()
        self._load_test_records()

    def submit_links_for_record(self, record: GraphRecord, user="main_account") -> None:
        """
        Submits a graph link for the node
        Args:
            record: Graph record for which graph link needs to be submitted
            new_submitter_ids: Whether to create new submitter ids for the graph link
            user: user having access to submit graph link
        """
        for prop in record.props:
            if (
                isinstance(record.props[prop], dict)
                and "submitter_id" in record.props[prop].keys()
            ):
                if prop in self.linked_test_submitter_ids.keys():
                    record.props[prop]["submitter_id"] = self.linked_test_submitter_ids[
                        prop
                    ]
                linked_node = self.get_node_with_submitter_id(
                    record.props[prop]["submitter_id"]
                )
                if not linked_node:
                    logger.error(
                        f"Record has a link to {record.props[prop]['submitter_id']} but we can't find that record"
                    )
                    raise

                self.submit_links_for_record(linked_node)
                self.submit_record(record=linked_node)

    def get_node_with_submitter_id(self, submitter_id: str) -> dict:
        """
        Returns the Graph record for the node containing the submitter_id
        Args:
            submitter_id: submitter_id for which graph record needs to be searched
        """
        all_nodes = self.test_records
        for node_name, node_details in all_nodes.items():
            if node_details.props["submitter_id"] == submitter_id:
                return all_nodes[node_name]

    def get_record_with_parent(self) -> GraphRecord:
        """
        Gets the first available child node
        """
        for record in self.test_records.values():
            for prop in record.props:
                if (
                    isinstance(record.props[prop], dict)
                    and "submitter_id" in record.props[prop].keys()
                ):
                    return record
        raise Exception("Did not find any record with parents")

    def query_record_fields(self, record: dict, filters={}) -> str:
        """
        Generates the graphql query and performs a query operation
        Args:
            record: Graph record for which query needs to be performed
            filters: pass filters for the query if needed
        """
        fields_string = self._fields_to_string(record.props)
        filter_string = ""
        if filters is not None and filters != {}:
            filter_string = self._filter_to_string(filters)
            filter_string = "(" + filter_string + ")"

        query_for_submission = (
            "{ "
            + record.node_name
            + " "
            + filter_string
            + " {"
            + fields_string
            + " } }"
        )
        return self.graphql_query(query_for_submission)

    def _fields_to_string(self, data: dict) -> str:
        """
        Converts the fields to query based string as needed to perform a graphql query operation
        Args:
            data: Graph record data
        """
        primitive_types = [int, float, bool, str]
        fields_string = ""
        for key, val in data.items():
            if type(val) in primitive_types:
                fields_string += f"\n{key}"
        return fields_string

    def _filter_to_string(self, filters: dict) -> str:
        """
        Converts the filters to query based string as needed to perform a graphql query operation
        Args:
            filters: Graph record filters
        """
        filter_string = []
        for key, val in filters.items():
            if isinstance(val, str):
                filter_string.append(f'{key}: "{val}"')
        return ", ".join(filter_string)

    def query_record_with_path_to(self, from_node: dict, to_node: dict) -> str:
        """
        Uses with_path_to filter to query from one node to another
        Args:
            from_node: First node to be queried from
            to_node : Last node to be queried to
        """
        query_to_submit = (
            "query Test { "
            + from_node.node_name
            + ' (order_by_desc: "created_datetime",with_path_to: { type: "'
            + to_node.node_name
            + '", submitter_id: "'
            + to_node.props["submitter_id"]
            + '"} ) { submitter_id } }'
        )
        return self.graphql_query(query_to_submit)

    def get_core_metadata(
        self,
        file,
        user,
        format="application/json",
        expected_status=200,
        invalid_authorization=False,
    ):
        """
        Returns the coremetadata information for the Graph record
        Args:
            file: Graph record
            user : user having permission to perform graphql operation
            format: format to be provided in headers
            expected_status: expected api response status
            invalid_authorization: If True set the authorization to invalid
        """
        min_sem_ver = "3.2.0"
        min_monthly_release = "2023.04.0"
        monthly_release_cutoff = "2020"

        auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
        response = auth.curl(path=self.GRAPHQL_VERSION_ENDPOINT)
        peregrine_version = response.json()["version"]
        url = f"{pytest.root_url}/api/search/coremetadata/"

        if peregrine_version:
            try:
                if Version(peregrine_version) < Version(min_sem_ver) or (
                    Version(peregrine_version) >= Version(monthly_release_cutoff)
                    and Version(peregrine_version) < Version(min_monthly_release)
                ):
                    # Legacy endpoint
                    url = "{pytest.root_url}/coremetadata/"
            except:
                logger.error(
                    "Can't parse or compare the peregrine version: don't user legacy url"
                )

        authorization = f"bearer {auth.get_access_token()}"
        if invalid_authorization:
            authorization = "invalid"
        headers = {
            "Authorization": authorization,
            "Accept": format,
        }
        response = requests.get(url=url + file.indexd_guid, headers=headers)
        assert response.status_code == expected_status, f"{response}"
        return response

    def verify_core_metadata_bibtex_contents(self, record, metadata):
        """
        Verifies the metadata bibtex contents is as expected
        Args:
            record: Graph Record
            metadata: coremetadata information
        """
        metadata = metadata.content.decode()
        assert (
            record.props["file_name"] in metadata
        ), f"file_name not matched/found.\n{record}\n{metadata}"
        assert (
            record.indexd_guid in metadata
        ), f"object_id not matched/found.\n{record}\n{metadata}"
        assert (
            record.props["type"] in metadata
        ), f"type not matched/found.\n{record}\n{metadata}"
        assert (
            record.props["data_format"] in metadata
        ), f"data_format not matched/found.\n{record}\n{metadata}"

    def see_core_metadata_error(self, metadata, message):
        """
        Verifies the metadata errors
        Args:
            metadata: coremetadata information
            message: expected message
        """
        if "message" not in metadata.json().keys():
            logger.error(f"Message key missing.\n{metadata.json()}")
            raise
        logger.info(metadata.json()["message"])
        if message != metadata.json()["message"]:
            logger.error(f"Expected message not found.\n{metadata.json()}")
            raise

    def verify_core_metadata_json_contents(self, record, metadata):
        """
        Verifies the metadata json contents is as expected
        Args:
            record: Graph Record
            metadata: coremetadata information
        """
        metadata = metadata.json()
        assert (
            record.props["file_name"] == metadata["file_name"]
        ), f"file_name not matched/found.\n{record}\n{metadata}"
        assert (
            record.indexd_guid == metadata["object_id"]
        ), f"object_id not matched/found.\n{record}\n{metadata}"
        assert (
            record.props["type"] == metadata["type"]
        ), f"type not matched/found.\n{record}\n{metadata}"
        assert (
            record.props["data_format"] == metadata["data_format"]
        ), f"data_format not matched/found.\n{record}\n{metadata}"
