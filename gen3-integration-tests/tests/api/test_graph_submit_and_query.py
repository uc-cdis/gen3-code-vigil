import os
import pytest

from cdislogging import get_logger

from services.peregrine import Peregrine
from services.sheepdog import Sheepdog


logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))

sheepdog = Sheepdog()
peregrine = Peregrine()
project_id = f"{sheepdog.program_name}-{sheepdog.project_code}"


@pytest.mark.sheepdog
@pytest.mark.peregrine
class TestGraphSubmitAndQuery:
    def test_delete_all_record_in_test_project(self):
        # clean up before starting the test suite
        # TODO probably shouldn't be a test but a setup or fixture
        for node_name in reversed(sheepdog.submission_order):
            query = f'query {{ {node_name} (project_id: "{project_id}") {{ id }} }}'
            result = peregrine.query(query).get("data", {}).get(node_name, [])
            for record in result:
                logger.info(
                    f"Pre-test clean up: deleting '{node_name}' record '{record['id']}'"
                )
                sheepdog.delete_record(record["id"])

    def test_submit_query_and_delete_records(self):
        """
        TODO
        """
        logger.info("Submitting test records")
        sheepdog.submit_all_test_records()

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

            # logger.info("Query an invalid field")
            # logger.info("Query with filter on a string attribute")
        finally:
            sheepdog.delete_all_test_records()
