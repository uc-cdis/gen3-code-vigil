"""
GUPPY SERVICE
"""
import os
import pytest

from cdislogging import get_logger
from services.guppy import Guppy


logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


@pytest.mark.guppy
class TestGuppyService:
    @pytest.mark.skip("Testing other test cases")
    def test_guppy_status(self):
        guppy = Guppy()
        assert guppy.validate_guppy_status("main_account", 200)

    @pytest.mark.skip("Results are broken")
    def test_guppy_test_query_1(self):
        """Scenario   : I want a list of patients (subjects) strictly younger
                     than 30 with a past stroke in ascending order of BMI.
        GUPPY File : testQuery1.json"""
        guppy = Guppy()
        queryFile = "testQuery1.json"
        responseFile = "testResponse1.json"
        assert guppy.validate_guppy_query(queryFile, responseFile, "main_account", 200)

    @pytest.mark.skip("Testing other test cases")
    def test_guppy_test_query_2(self):
        """Scenario   : I want a total count of patients matching the
                     filter in the scenario above.
        GUPPY File : testQuery2.json"""
        guppy = Guppy()
        queryFile = "testQuery2.json"
        responseFile = "testResponse2.json"
        assert guppy.validate_guppy_query(queryFile, responseFile, "main_account", 200)

    @pytest.mark.skip("Results are broken")
    def test_guppy_test_query_3(self):
        """Scenario   : I want a high-level overview of the data
                     in the database as it pertains to stroke
                     occurrence and age groups represented.
        GUPPY File : testQuery3.json"""
        guppy = Guppy()
        queryFile = "testQuery3.json"
        responseFile = "testResponse3.json"
        assert guppy.validate_guppy_query(queryFile, responseFile, "main_account", 200)

    @pytest.mark.skip("Error from API response")
    def test_guppy_test_query_4(self):
        """Scenario   : Range-stepped database check of age groups.
        GUPPY File : testQuery4.json"""
        guppy = Guppy()
        queryFile = "testQuery4.json"
        responseFile = "testResponse4.json"
        assert guppy.validate_guppy_query(queryFile, responseFile, "main_account", 200)

    @pytest.mark.skip("Testing other test cases")
    def test_guppy_test_query_5(self):
        """Scenario   : I would like to list the fields on the subject document.
        GUPPY File : testQuery5.json"""
        guppy = Guppy()
        queryFile = "testQuery5.json"
        responseFile = "testResponse5.json"
        assert guppy.validate_guppy_query(queryFile, responseFile, "main_account", 200)

    @pytest.mark.skip("Results are broken")
    def test_guppy_test_query_6(self):
        """Scenario   : I want to render a set of visualizations
                     summarizing data in the commons.
        GUPPY File : testQuery6.json"""
        guppy = Guppy()
        queryFile = "testQuery6.json"
        responseFile = "testResponse6.json"
        assert guppy.validate_guppy_query(queryFile, responseFile, "main_account", 200)

    @pytest.mark.skip("Error from API response")
    def test_guppy_test_query_7(self):
        """Scenario   : I want to make multiple histograms describing
                     the BMI parameter to gain an understanding of
                     its distribution.
        GUPPY File : testQuery7.json"""
        guppy = Guppy()
        queryFile = "testQuery7.json"
        responseFile = "testResponse7.json"
        assert guppy.validate_guppy_query(queryFile, responseFile, "main_account", 200)

    @pytest.mark.skip("Error from API response")
    def test_guppy_test_query_8(self):
        """Scenario   : I want to make a filtering query without
                     worrying about paginating the results, or
                     whether the result will be > 10k records.
        GUPPY File : testQuery8.json"""
        guppy = Guppy()
        queryFile = "testQuery8.json"
        responseFile = "testResponse8.json"
        assert guppy.validate_guppy_query(queryFile, responseFile, "main_account", 200)
