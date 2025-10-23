"""
ENV SANITY
"""

import os

import pytest
from gen3.auth import Gen3Auth
from utils import logger


@pytest.mark.env_sanity
@pytest.mark.skipif(
    "chore/apply_" not in os.getenv("BRANCH"),
    reason="Current PR is not a release PR",
)
class TestEnvSanity:
    @classmethod
    def setup_class(cls):
        cls.BASE_URL = f"{pytest.root_url}"

    def test_service_versions(self):
        """
        Scenario: Test service versions
        Steps:
            1. Get list of deployments on the current namespace
            2. Get the service version by calling the service version endpoint
            3. Validate the service version matches the version of the deployment
        """
        logger.info("Running Env Sanity Test")
        release_version = os.getenv("BRANCH").split("_")[1]
        service_endpoints = {
            "audit": "/audit/_version",
            "fence": "/user/_version",
            "gen3-user-data-library": "/library/_version",
            "guppy": "/guppy/_version",
            "indexd": "/index/_version",
            "metadata-service": "/mds/version",  # version
            "peregrine": "/peregrine/_version",
            "requestor": "/requestor/_version",
            "sheepdog": "/api/_version",
            "wts": "/wts/_version",
        }
        failed_services = []
        for service in pytest.deployed_services.splitlines():
            service_name = service.replace("-deployment", "")
            if service_name in service_endpoints:
                try:
                    logger.info(
                        f"Service {service_name} found, checking service version"
                    )
                    auth = Gen3Auth(
                        refresh_token=pytest.api_keys["main_account"],
                        endpoint=pytest.root_url,
                    )
                    url = self.BASE_ENDPOINT + "/_status"
                    response = auth.curl(path=url)
                    assert (
                        response.status_code == 200
                    ), f"Expected 200 but got {response.status_code}"
                    data = response.json()
                    logger.info(f"Got version {data['version']}")
                    assert (
                        data["version"] == release_version
                    ), f"Expected {release_version} but got {data['version']}"
                except Exception as e:
                    logger.info(f"Got exception for {service_name}: {e}")
                    failed_services.append(service_name)

        if len(failed_services) > 0:
            raise Exception(
                f"List of services where version validation failed: {failed_services}"
            )
