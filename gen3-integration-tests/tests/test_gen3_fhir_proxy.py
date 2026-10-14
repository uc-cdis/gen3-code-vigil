"""
gen3-fhir-proxy Integration Tests

Tests for the FHIR proxy service endpoints including:
- SMART on FHIR discovery
- FHIR CapabilityStatement
- Patient resource search and retrieval
- Authentication / authorization enforcement
"""

import pytest
from services.fhir_proxy import FhirProxy
from utils import logger


@pytest.mark.skipif(
    "gen3-fhir-proxy" not in pytest.deployed_services,
    reason="gen3-fhir-proxy is not running on this environment",
)
@pytest.mark.gen3_fhir_proxy
class TestFhirProxy:
    @classmethod
    def setup_class(cls):
        cls.fhir = FhirProxy()

    def test_status(self):
        """
        Scenario: Health check endpoint returns 200
        Steps:
            1. GET /fhir/_status
            2. Verify response status is 200
        """
        response = self.fhir.get_status()
        assert (
            response.status_code == 200
        ), f"Expected 200 from /fhir/_status but got {response.status_code}"

    def test_metadata_capability_statement(self):
        """
        Scenario: FHIR CapabilityStatement is returned without authentication
        Steps:
            1. GET /fhir/metadata (no auth)
            2. Verify 200 response
            3. Verify response body contains resourceType CapabilityStatement
        """
        response = self.fhir.get_metadata()
        assert (
            response.status_code == 200
        ), f"Expected 200 from /fhir/metadata but got {response.status_code}"
        body = response.json()
        assert (
            body.get("resourceType") == "CapabilityStatement"
        ), f"Expected resourceType CapabilityStatement but got: {body.get('resourceType')}"

    def test_smart_configuration(self):
        """
        Scenario: SMART App Launch discovery document is returned without authentication
        Steps:
            1. GET /fhir/.well-known/smart-configuration (no auth)
            2. Verify 200 response
            3. Verify required SMART fields are present
        """
        response = self.fhir.get_smart_configuration()
        assert (
            response.status_code == 200
        ), f"Expected 200 from /fhir/.well-known/smart-configuration but got {response.status_code}"
        body = response.json()
        assert (
            "authorization_endpoint" in body
        ), "SMART configuration missing authorization_endpoint"
        assert "token_endpoint" in body, "SMART configuration missing token_endpoint"
        assert "capabilities" in body, "SMART configuration missing capabilities"

    def test_patient_search_authenticated(self):
        """
        Scenario: Authenticated patient search returns a FHIR Bundle
        Steps:
            1. GET /fhir/Patient with valid credentials
            2. Verify 200 response
            3. Verify response is a FHIR Bundle
        """
        response = self.fhir.search_patients()
        assert (
            response.status_code == 200
        ), f"Expected 200 from GET /fhir/Patient but got {response.status_code}"
        body = response.json()
        assert (
            body.get("resourceType") == "Bundle"
        ), f"Expected resourceType Bundle but got: {body.get('resourceType')}"

    def test_patient_post_search_authenticated(self):
        """
        Scenario: POST-based patient search returns a FHIR Bundle
        Steps:
            1. POST /fhir/Patient/_search with valid credentials
            2. Verify 200 response
            3. Verify response is a FHIR Bundle
        """
        response = self.fhir.post_search_patients()
        assert (
            response.status_code == 200
        ), f"Expected 200 from POST /fhir/Patient/_search but got {response.status_code}"
        body = response.json()
        assert (
            body.get("resourceType") == "Bundle"
        ), f"Expected resourceType Bundle but got: {body.get('resourceType')}"

    def test_patient_search_unauthenticated(self):
        """
        Scenario: Unauthenticated patient search is rejected
        Steps:
            1. GET /fhir/Patient without any credentials
            2. Verify 401 response
        """
        response = self.fhir.search_patients_unauthenticated()
        assert (
            response.status_code == 401
        ), f"Expected 401 from unauthenticated /fhir/Patient but got {response.status_code}"

    def test_patient_get_by_id_not_found(self):
        """
        Scenario: Fetching a non-existent patient returns 404
        Steps:
            1. GET /fhir/Patient/nonexistent-id with valid credentials
            2. Verify 404 response
        """
        response = self.fhir.get_patient("nonexistent-patient-id-000")
        assert (
            response.status_code == 404
        ), f"Expected 404 for non-existent patient but got {response.status_code}"
