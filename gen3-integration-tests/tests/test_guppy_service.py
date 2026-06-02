"""
GUPPY SERVICE
"""

import json
import os

import pytest
from gen3.auth import Gen3Auth
from gen3.query import Gen3Query
from services.guppy import Guppy
from utils import TEST_DATA_PATH_OBJECT, logger


@pytest.mark.skipif(
    "guppy" not in pytest.deployed_services,
    reason="guppy service is not running on this environment",
)
@pytest.mark.guppy
class TestGuppyService:
    @classmethod
    def setup_class(cls):
        guppy = Guppy()
        # this may be needed once these new tests are used for manifest PRs
        # TODO: remove if not needed
        # assert mutate_manifest_for_guppy_test(pytest.namespace)
        assert guppy.validate_guppy_status("main_account", 200)

    def test_guppy_test_query_1(self):
        """
        Scenario:
        I want a list of patients (subjects) strictly younger
        than 30 with a past stroke in ascending order of BMI.

        Steps:
            1. Call API guppy/graphql using Query in test_query1.json
            2. Validate API response against data in tesResponse1.json
        """
        guppy = Guppy()
        queryFile = "test_query1.json"
        responseFile = "test_response1.json"
        queryType = "data"
        assert guppy.validate_guppy_query(
            queryFile, responseFile, queryType, "main_account", 200
        )

    def test_guppy_test_query_2(self):
        """
        Scenario:
        I want a total count of patients matching the
        filter in the scenario above.

        Steps:
            1. Call API guppy/graphql using Query in test_query2.json
            2. Validate API response against data in tesResponse2.json
        """
        guppy = Guppy()
        queryFile = "test_query2.json"
        responseFile = "test_response2.json"
        queryType = "aggregation"
        assert guppy.validate_guppy_query(
            queryFile, responseFile, queryType, "main_account", 200
        )

    def test_guppy_test_query_3(self):
        """
        Scenario:
        I want a high-level overview of the data
        in the database as it pertains to stroke
        occurrence and age groups represented.

        Steps:
            1. Call API guppy/graphql using Query in test_query3.json
            2. Validate API response against data in tesResponse3.json
        """
        guppy = Guppy()
        queryFile = "test_query3.json"
        responseFile = "test_response3.json"
        queryType = "histogram"
        assert guppy.validate_guppy_query(
            queryFile, responseFile, queryType, "main_account", 200
        )

    def test_guppy_test_query_4(self):
        """
        Scenario:
        Range-stepped database check of age groups.

        Steps:
            1. Call API guppy/graphql using Query in test_query4.json
            2. Validate API response against data in tesResponse4.json
        """
        guppy = Guppy()
        queryFile = "test_query4.json"
        responseFile = "test_response4.json"
        queryType = "histogram"
        assert guppy.validate_guppy_query(
            queryFile, responseFile, queryType, "main_account", 200
        )

    def test_guppy_test_query_5(self):
        """
        Scenario:
        I would like to list the fields on the subject document.

        Steps:
            1. Call API guppy/graphql using Query in test_query5.json
            2. Validate API response against data in tesResponse5.json
        """
        guppy = Guppy()
        queryFile = "test_query5.json"
        responseFile = "test_response5.json"
        queryType = "mapping"
        assert guppy.validate_guppy_query(
            queryFile, responseFile, queryType, "main_account", 200
        )

    def test_guppy_test_query_6(self):
        """
        Scenario:
        I want to render a set of visualizations
        summarizing data in the commons.

        Steps:
            1. Call API guppy/graphql using Query in test_query6.json
            2. Validate API response against data in tesResponse6.json
        """
        guppy = Guppy()
        queryFile = "test_query6.json"
        responseFile = "test_response6.json"
        queryType = "histogram"
        assert guppy.validate_guppy_query(
            queryFile, responseFile, queryType, "main_account", 200
        )

    def test_guppy_test_query_7(self):
        """
        Scenario:
        I want to make multiple histograms describing the BMI
        parameter to gain an understanding of its distribution.

        Steps:
            1. Call API guppy/graphql using Query in test_query7.json
            2. Validate API response against data in tesResponse7.json
        """
        guppy = Guppy()
        queryFile = "test_query7.json"
        responseFile = "test_response7.json"
        queryType = "histogram"
        assert guppy.validate_guppy_query(
            queryFile, responseFile, queryType, "main_account", 200
        )

    def test_guppy_test_query_8(self):
        """Scenario:
        I want to make a filtering query without worrying about
        paginating the results, or whether the result will be > 10k records.

        Steps:
            1. Call API guppy/download using Query in test_query8.json
            2. Validate API response against data in tesResponse8.json
        """
        guppy = Guppy()
        queryFile = "test_query8.json"
        responseFile = "test_response8.json"
        queryType = "download"
        assert guppy.validate_guppy_query(
            queryFile,
            responseFile,
            queryType,
            "main_account",
            200,
            endpoint="/download",
        )

    def test_gen3_query_raw_data_download(self):
        """
        Scenario: Download raw data using Gen3Query from gen3sdk

        Steps:
            1. Call raw_data_download() to download the data
            2. Verify the number of records returned is 100 (Subject index has 100 records)
        """
        auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )
        gen3query = Gen3Query(auth_provider=auth)
        response = gen3query.raw_data_download(
            data_type="subject",
            fields=[
                "file_id",
                "project_id",
                "submitter_id",
            ],
        )
        assert len(response) == 100, f"Expected 100 records but got {len(response)}"

    def test_gen3_query_graphql_query(self):
        """
        Scenario: Perform graphql query using Gen3Query from gen3sdk

        Steps:
            1. Call graphql_query() to perform graphql query
            2.
        """
        guppy = Guppy()
        auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )
        gen3query = Gen3Query(auth_provider=auth)

        query_file = json.loads(
            (TEST_DATA_PATH_OBJECT / "guppy" / "test_query1.json").read_text(
                encoding="UTF-8"
            )
        )
        response_file = (
            TEST_DATA_PATH_OBJECT / "guppy" / "test_response1.json"
        ).read_text(encoding="UTF-8")
        response = gen3query.graphql_query(
            query_string=query_file["query"],
            variables=query_file["variables"],
        )
        actualResponse = response["data"]["subject"]
        expectedResponse = eval(response_file)["data"]["subject"]
        assert guppy.match_data_query(actualResponse, expectedResponse)
