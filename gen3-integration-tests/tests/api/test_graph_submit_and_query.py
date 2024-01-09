import os
import pytest

from cdislogging import get_logger
from gen3.auth import Gen3Auth
from gen3.submission import Gen3SubmissionQueryError

from services.peregrine import Peregrine
from services.sheepdog import Sheepdog


logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.sheepdog
@pytest.mark.peregrine
class TestGraphSubmitAndQuery:
    def test_submit_query_and_delete_records(self):
        """
        Submit graph data and perform various queries.

        Steps:
        - Submit graph data
        - Check that querying the records return the submitted data
        - Check that querying an invalid property errors
        - Check that filtering on string properties works
        - Check that node count queries work
        - Delete the graph data
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        sheepdog = Sheepdog(auth=auth)
        peregrine = Peregrine(auth=auth)
        project_id = f"{sheepdog.program_name}-{sheepdog.project_code}"
        sheepdog.create_program_and_project()
        sheepdog.delete_all_records_in_test_project(peregrine)

        logger.info("Submitting test records")
        sheepdog.submit_all_test_records()

        new_records = []
        try:
            logger.info(
                "For each node, query all the properties and check that the response matches"
            )
            for node_name, record in sheepdog.test_records.items():
                primitive_props = [
                    prop
                    for prop in record.props.keys()
                    if type(record.props[prop]) != dict
                ]
                props_str = " ".join(primitive_props)
                query = f'query {{ {node_name} (project_id: "{project_id}") {{ {props_str} }} }}'
                received_data = (
                    peregrine.query(query).get("data", {}).get(node_name, [])
                )
                assert (
                    len(received_data) == 1
                ), "Submitted 1 record so expected query to return 1 record"
                for prop in primitive_props:
                    assert received_data[0][prop] == record.props[prop]

            # use a node at the bottom of the tree to it's easier to delete nodes in the right order
            node_name = sheepdog.submission_order[-1]

            logger.info("Query an invalid properyu")
            query = f'query {{ {node_name} (project_id: "{project_id}") {{ prop_does_not_exist }} }}'
            with pytest.raises(
                Gen3SubmissionQueryError,
                match=f'Cannot query field "prop_does_not_exist" on type "{node_name}".',
            ):
                peregrine.query(query)

            logger.info("Query with filter on a string property")
            string_prop = [
                prop for prop in record.props.keys() if type(record.props[prop]) == str
            ][0]
            string_prop_value = record.props[string_prop]
            query = f'query {{ {node_name} (project_id: "{project_id}", {string_prop}: "{string_prop_value}") {{ {string_prop} }} }}'
            received_data = peregrine.query(query).get("data", {}).get(node_name, [])
            assert len(received_data) == 1
            assert received_data[0][string_prop] == string_prop_value

            logger.info("Query node count before and after submitting a new record")
            result = peregrine.query_node_count(node_name)
            count = result.get("data", {}).get(f"_{node_name}_count")
            new_records.append(sheepdog.submit_new_record(node_name))
            result = peregrine.query_node_count(node_name)
            assert result.get("data", {}).get(f"_{node_name}_count") == count + 1
        finally:
            sheepdog.delete_records([record.sheepdog_id for record in new_records])
            sheepdog.delete_all_test_records()

    # TODO add tests:
    # submit node unauthenticated
    # submit node without parent
    # test with_path_to - first to last node
    # test with_path_to - last to first node
    # submit data node with consent codes
