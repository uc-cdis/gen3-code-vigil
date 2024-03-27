"""
GUPPY SERVICE
"""
import os
import pytest

from cdislogging import get_logger
from utils.gen3_admin_tasks import run_guppy_gen3_setup
from services.guppy import Guppy


logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.guppy
class TestGuppyService:
    @classmethod
    def setup_class(cls):
        guppy = Guppy()
        assert run_guppy_gen3_setup(pytest.namespace)
        assert guppy.validate_guppy_status("main_account", 200)

    def test_guppy_test_query_1(self):
        """
        Scenario:
        I want a list of patients (subjects) strictly younger
        than 30 with a past stroke in ascending order of BMI.

        Steps:
            1. Call API guppy/graphql using Query in testQuery1.json
            2. Validate API response against data in tesResponse1.json
        """
        guppy = Guppy()
        queryFile = "testQuery1.json"
        responseFile = "testResponse1.json"
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
            1. Call API guppy/graphql using Query in testQuery2.json
            2. Validate API response against data in tesResponse2.json
        """
        guppy = Guppy()
        queryFile = "testQuery2.json"
        responseFile = "testResponse2.json"
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
            1. Call API guppy/graphql using Query in testQuery3.json
            2. Validate API response against data in tesResponse3.json
        """
        guppy = Guppy()
        queryFile = "testQuery3.json"
        responseFile = "testResponse3.json"
        queryType = "histogram"
        assert guppy.validate_guppy_query(
            queryFile, responseFile, queryType, "main_account", 200
        )

    @pytest.mark.wip("Error from API response")
    def test_guppy_test_query_4(self):
        """
        Scenario:
        Range-stepped database check of age groups.

        Steps:
            1. Call API guppy/graphql using Query in testQuery4.json
            2. Validate API response against data in tesResponse4.json
        """
        guppy = Guppy()
        queryFile = "testQuery4.json"
        responseFile = "testResponse4.json"
        queryType = "histogram"
        assert guppy.validate_guppy_query(
            queryFile, responseFile, queryType, "main_account", 200
        )

    def test_guppy_test_query_5(self):
        """
        Scenario:
        I would like to list the fields on the subject document.

        Steps:
            1. Call API guppy/graphql using Query in testQuery5.json
            2. Validate API response against data in tesResponse5.json
        """
        guppy = Guppy()
        queryFile = "testQuery5.json"
        responseFile = "testResponse5.json"
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
            1. Call API guppy/graphql using Query in testQuery6.json
            2. Validate API response against data in tesResponse6.json
        """
        guppy = Guppy()
        queryFile = "testQuery6.json"
        responseFile = "testResponse6.json"
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
            1. Call API guppy/graphql using Query in testQuery7.json
            2. Validate API response against data in tesResponse7.json
        """
        guppy = Guppy()
        queryFile = "testQuery7.json"
        responseFile = "testResponse7.json"
        queryType = "histogram"
        assert guppy.validate_guppy_query(
            queryFile, responseFile, queryType, "main_account", 200
        )

    def test_guppy_test_query_8(self):
        """Scenario:
        I want to make a filtering query without worrying about
        paginating the results, or whether the result will be > 10k records.

        Steps:
            1. Call API guppy/download using Query in testQuery8.json
            2. Validate API response against data in tesResponse8.json
        """
        guppy = Guppy()
        queryFile = "testQuery8.json"
        responseFile = "testResponse8.json"
        queryType = "download"
        assert guppy.validate_guppy_query(
            queryFile,
            responseFile,
            queryType,
            "main_account",
            200,
            endpoint="/download",
        )
