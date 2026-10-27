"""Service module for gen3-fhir-proxy load testing."""

import os

from gen3.auth import Gen3Auth
from gen3.tools.metadata.metadata_mapping import Gen3MetaDataException


class FhirProxyService:
    def __init__(self, hostname: str = None):
        self.hostname = hostname or os.getenv("HOSTNAME")
        self.protocol = os.getenv("HOSTNAME_PROTOCOL", "https")
        self.base_url = f"{self.protocol}://{self.hostname}/fhir-proxy"
        self.auth = Gen3Auth(
            refresh_file=os.path.expanduser("~/.gen3/credentials.json")
        )

    def get_access_token(self) -> str:
        """Fetch a valid access token for proxy authorization."""
        return self.auth.get_access_token()

    def get_headers(self) -> dict:
        """Construct required headers for fhir-proxy requests."""
        return {
            "Authorization": f"Bearer {self.get_access_token()}",
            "Accept": "application/fhir+json",
        }
