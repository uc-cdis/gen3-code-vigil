"""
GUPPY SERVICE
"""

import os

import pytest
from services.guppy import Guppy
from utils import logger


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
