import json
import os
import random
import time

import pytest
import utils.gen3_admin_tasks as gat
from pages.discovery import DiscoveryPage
from pages.login import LoginPage
from pages.study_registration import StudyRegistrationPage
from services.metadataservice import MetadataService
from services.requestor import Requestor
from utils import TEST_DATA_PATH_OBJECT, logger
from utils.test_execution import screenshot


@pytest.mark.requestor
@pytest.mark.mds
@pytest.mark.study_registration
@pytest.mark.skipif(
    "portal" not in pytest.deployed_services,
    reason="portal service is not running on this environment",
)
@pytest.mark.wip
@pytest.mark.portal
@pytest.mark.skipif(
    not pytest.use_agg_mdg_flag,
    reason="USE_AGG_MDS is not set or is false in manifest",
)
class TestStudyRegistration(object):
    @classmethod
    def setup_class(cls):
        cls.variables = {}
        cls.variables["request_ids"] = []
        cls.variables["cedar_UUID"] = "c5891154-750a-4ed7-83b7-7cac3ddddae6"
        cls.variables["policy_id"] = (
            "study.9675420_mds_gateway_cedar_study_registrant_mds_user_cedar_user"
        )
        cls.variables["application_id"] = str(random.randint(10000000, 99999999))

    @classmethod
    def teardown_class(cls):
        requestor = Requestor()
        mds = MetadataService()
        req_data = {
            "username": pytest.users["user2_account"],
            "policy_id": cls.variables["policy_id"],
            "revoke": True,
        }
        revoke_request = requestor.create_request_with_auth_header(
            username=req_data["username"],
            policy_id=req_data["policy_id"],
            revoke=req_data["revoke"],
        )
        assert (
            revoke_request.status_code == 201
        ), f"Failed to create revoke request with status_code : {revoke_request.status_code}"
        revoke_request_data = revoke_request.json()
        if "request_id" in revoke_request_data:
            revoke_request_id = revoke_request_data["request_id"]
            cls.variables["request_ids"].append(revoke_request_id)
        else:
            logger.info("Revoke request_id was not found ...")
        revoke_status = requestor.request_signed(revoke_request_id)
        if revoke_status == "SIGNED":
            logger.info(f"Access revoked for user")

        # Delete all the request_ids after the test is executed
        for request_id in cls.variables["request_ids"]:
            requestor.request_delete(request_id)
            logger.info(f"Request {request_id} deleted")

        # Deleting dummy metadata with application_id
        mds.delete_metadata(cls.variables["application_id"])

    def test_register_new_study(self, page):
        """
        Scenario: Register a new study
        Steps:
            1. Upload a dummy metadata record
            2. Login with user2 user and navigate to discovery page
            3. Request access to register study
            4. Register study with CEDAR UUID
            5. Run aggMDS job and check if the study is registered
        """
        login_page = LoginPage()
        mds = MetadataService()
        requestor = Requestor()
        discovery_page = DiscoveryPage()
        study_register = StudyRegistrationPage()
        # Get UID field name from portal config
        portal_config = gat.get_portal_config()
        uid_field_name = (
            portal_config.get("discoveryConfig", {})
            .get("minimalFieldMapping", {})
            .get("uid", None)
        )
        assert uid_field_name is not None
        # Update the study metadata field with application id
        filepath = TEST_DATA_PATH_OBJECT / "study_registration" / "study.json"
        with open(filepath, "r") as file:
            study_metadata = json.load(file)
        # Update fields in studyRegistration study.json with application_id
        study_metadata["gen3_discovery"]["appl_id"] = self.variables["application_id"]
        study_metadata["gen3_discovery"][uid_field_name] = self.variables[
            "application_id"
        ]
        # Storing project_title and project_number for validation in test
        study_name = study_metadata["gen3_discovery"]["study_metadata"]["minimal_info"][
            "study_name"
        ]
        project_number = study_metadata["gen3_discovery"]["project_number"]
        access_form_title = f"{study_name} - {project_number}"
        project_title = study_metadata["gen3_discovery"]["project_title"]
        nih_application_id = study_metadata["gen3_discovery"]["study_metadata"][
            "metadata_location"
        ]["nih_application_id"]
        # Writing the new fields to study.json
        with open(filepath, "w", encoding="utf8") as file:
            json.dump(study_metadata, file, indent=4)

        # Creating a metadata record from study_metadata
        mds.create_metadata(self.variables["application_id"], study_metadata)

        # Updating the study_metadata with PUT request
        study_metadata["gen3_discovery"]["registration_authz"] = "/study/9675420"
        mds.update_metadata(self.variables["application_id"], study_metadata)

        # Get mds record from mds/metadata endpoint and verify the metadata
        record = mds.get_metadata(self.variables["application_id"])
        assert (
            record["gen3_discovery"]["project_title"] == project_title
        ), f"Expected project title to be {project_title}, but got {record['gen3_discovery']['project_title']}."
        assert (
            record["_guid_type"] == "unregistered_discovery_metadata"
        ), f"Expected _guid_type to be 'unregistered_discovery_metadata' , but got {record['_guid_type']}."

        # Login with user2 and go to discovery page
        login_page.go_to(page)
        login_page.login(page, user="user2_account")
        discovery_page.go_to(page)
        screenshot(page, "DiscoveryPage")

        # # Request access to register study by filling out registration form
        study_register.search_study(page, self.variables["application_id"])
        study_register.click_request_access_to_register(page)
        study_register.fill_request_access_form(
            page, pytest.users["user2_account"], access_form_title
        )

        # Update the request_id to Signed Status
        request_id = requestor.get_request_id(
            self.variables["policy_id"], "user2_account"
        )
        if request_id:
            logger.debug(f"Request ID : {request_id}")
            self.variables["request_ids"].append(request_id)
        else:
            logger.info("Request was not found")
        requestor.request_signed(request_id)
        status = requestor.get_request_status(request_id)
        if status == "SIGNED":
            logger.info(f"{request_id} is updated to SIGNED status")

        # Navigate to discovery page and register study
        time.sleep(30)
        page.reload()
        discovery_page.go_to(page)
        study_register.search_study(page, self.variables["application_id"])
        study_register.click_register_study(page)

        cedar_uuid = self.variables["cedar_UUID"]
        study_name = f"{project_number} : TEST : {nih_application_id}"
        study_register.fill_registration_form(page, cedar_uuid, study_name)

        # After registering the study, run metadata-agg-sync job
        gat.run_gen3_job("metadata-aggregate-sync", test_env_namespace=pytest.namespace)
        # # TODO : check the job pod status with kube-check-pod jenkins job
        gat.check_job_pod(
            "metadata-aggregate-sync", "gen3job", test_env_namespace=pytest.namespace
        )

        linked_record = mds.get_aggregate_metadata(self.variables["application_id"])
        logger.debug(f"Linked Record : {linked_record}")
        is_registered = linked_record["gen3_discovery"].get("is_registered")
        assert (
            is_registered is True
        ), f"Failed to register study with {self.variables['application_id']}"
