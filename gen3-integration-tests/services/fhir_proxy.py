"""Service module for gen3-fhir-proxy integration tests."""

import pytest
import requests
from gen3.auth import Gen3Auth
from utils import logger


class FhirProxy:
    def __init__(self):
        self.BASE_URL = f"{pytest.root_url}"
        self.FHIR_ENDPOINT = "/fhir"

    def _auth(self, user: str = "main_account") -> Gen3Auth:
        return Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=self.BASE_URL)

    def get_metadata(self) -> requests.Response:
        """GET /fhir/metadata — CapabilityStatement, no auth required."""
        response = requests.get(
            f"{self.BASE_URL}{self.FHIR_ENDPOINT}/metadata",
            headers={"Accept": "application/fhir+json"},
        )
        return response

    def get_smart_configuration(self) -> requests.Response:
        """GET /fhir/.well-known/smart-configuration — SMART discovery, no auth required."""
        response = requests.get(
            f"{self.BASE_URL}{self.FHIR_ENDPOINT}/.well-known/smart-configuration",
            headers={"Accept": "application/json"},
        )
        return response

    def get_status(self) -> requests.Response:
        """GET /fhir/_status — health check, no auth required."""
        response = requests.get(f"{self.BASE_URL}{self.FHIR_ENDPOINT}/_status")
        return response

    def search_patients(
        self, params: str = None, user: str = "main_account"
    ) -> requests.Response:
        """GET /fhir/Patient — patient search with auth."""
        auth = self._auth(user)
        path = f"{self.FHIR_ENDPOINT}/Patient"
        if params:
            path = f"{path}?{params}"
        return auth.curl(path=path)

    def post_search_patients(
        self, body: dict = None, user: str = "main_account"
    ) -> requests.Response:
        """POST /fhir/Patient/_search — POST-based patient search with auth."""
        auth = self._auth(user)
        url = f"{self.BASE_URL}{self.FHIR_ENDPOINT}/Patient/_search"
        response = requests.post(
            url,
            data=body or {},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            auth=auth,
        )
        logger.info(f"POST /fhir/Patient/_search status: {response.status_code}")
        return response

    def get_patient(
        self, patient_id: str, user: str = "main_account"
    ) -> requests.Response:
        """GET /fhir/Patient/{id} — single patient by ID with auth."""
        auth = self._auth(user)
        return auth.curl(path=f"{self.FHIR_ENDPOINT}/Patient/{patient_id}")

    def search_patients_unauthenticated(self) -> requests.Response:
        """GET /fhir/Patient without auth — should return 401."""
        response = requests.get(
            f"{self.BASE_URL}{self.FHIR_ENDPOINT}/Patient",
            headers={"Accept": "application/fhir+json"},
        )
        return response
