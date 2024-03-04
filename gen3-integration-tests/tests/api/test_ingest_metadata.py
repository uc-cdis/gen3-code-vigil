import json
import os
import uuid
import pytest
import requests

import asyncio

from cdislogging import get_logger
from gen3.auth import Gen3Auth
from gen3.metadata import Gen3Metadata
from gen3.jobs import Gen3Jobs, DBGAP_METADATA_JOB, INGEST_METADATA_JOB
from gen3.utils import get_or_create_event_loop_for_thread

from utils import TEST_DATA_PATH_OBJECT
import utils.gen3_admin_tasks as gat

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))

# Issue with get_config:
#
# If all tests are run there is sometimes as an error from 'get_configuration_files'.
# [2024-03-01 16:26:06,344][utils.gen3_admin_tasks][  ERROR] Build number not found
# The jenkins job restarts and runs but the test never gets a build number and will error out.
# Commenting out one or two of the tests usually works.

# Setup:
#
# I copied the 'sower' entry from the 'manifest.json' for qa-jcoin
# https://github.com/uc-cdis/gitops-qa/blob/74ab2bc9202f8706a86463c9861f7ce9ac61b5cd/qa-jcoin.planx-pla.net/manifest.json#L81
# into the 'manifest.json' for my dev environment.
# The 'serviceAccountName' was changed to match the environment.
#
# I added the following 'env' configuration in the 'container' section
# of 'get-dbgap-metadata'to force reading of the testDbGaPURL for the
# 'test_get_dbgap_metadata_and_ingest' test:
#
#   "env": [{
#     "name": "DBGAP_STUDY_ENDPOINT",
#     "value": "https://cdis-presigned-url-test.s3.amazonaws.com/test-dbgap-mock-study.xml"
#   }],
#


@pytest.mark.mds
class TestIngestMetadata:

    # This test replicates Scenario #1 in the original test.
    def test_dispatch_ingest_metadata(self):
        """
        Steps:
        1. Submit an ingest-metadata-manifest sower job and verify pod creation.
        2. Verify that the submitted study-id is in MDS.
        3. Delete the metadata record and verify deletion.

        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        jobs = Gen3Jobs(auth_provider=auth)
        mds = Gen3Metadata(auth_provider=auth)
        hostname = os.getenv("HOSTNAME")

        logger.info("# Dispatch sower job")
        dispatch = (
            TEST_DATA_PATH_OBJECT / "sower" / "dispatch-ingest-metadata.json"
        ).read_text(encoding="UTF-8")
        dispatch_json = json.loads(dispatch)
        logger.info(f"URL: {dispatch_json['ingest_metadata_input']['URL']}")
        logger.info(f"Study Id: {dispatch_json['ingest_metadata_input']['study_id']}")

        # clear out metadata for this study
        test_guid = dispatch_json.get("ingest_metadata_input").get("study_id")
        try:
            mds.delete(test_guid)
        except:
            logger.debug(f"Guid not present in MDS: {test_guid}")

        ingest_metadata_input = {
            "URL": dispatch_json["ingest_metadata_input"]["URL"],
            "metadata_source": dispatch_json["ingest_metadata_input"][
                "metadata_source"
            ],
            "host": hostname,
        }
        logger.info(f"Dispatch input: {ingest_metadata_input}")
        loop = get_or_create_event_loop_for_thread()
        job_output = loop.run_until_complete(
            jobs.async_run_job_and_wait(
                job_name=INGEST_METADATA_JOB, job_input=ingest_metadata_input
            )
        )
        assert job_output.get("output")

        # check that the study_id is in metadata.
        dbgap_guids = mds.query("dbgap=*")
        assert (
            test_guid in dbgap_guids
        ), f"dbgap guids does not contain test_guid {test_guid}"

        try:
            study_metadata = mds.get(test_guid)
            logger.info(f"Study metadata {study_metadata}")
        except:
            logger.error(
                f"Could not get metadata. Guid not present in MDS: {test_guid}"
            )
        assert study_metadata.get("dbgap").get("sra_sample_id") == dispatch_json.get(
            "expected"
        ).get(
            "sra_sample_id"
        ), f"Metadata for {test_guid} does not match expected sra_sample_id."

        try:
            mds.delete(test_guid)
        except:
            logger.debug(
                f"Could not delete metadata. Guid not present in MDS: {test_guid}"
            )

    # This test replicates Scenarios #2 and #3 from the original test.
    @pytest.mark.parametrize("match_type", ["exact_match", "partial_match"])
    def test_get_dbgap_metadata_and_ingest(self, match_type):
        """
        Steps:
        1. Submit an get-dbgap-metadata sower job and verify pod creation.
        2. Submit the dbgap metadata into MDS and verify.
        3. Delete the metadata record and verify deletion.

        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        mds = Gen3Metadata(auth_provider=auth)
        jobs = Gen3Jobs(auth_provider=auth)
        hostname = os.getenv("HOSTNAME")

        logger.info("# Dispatch sower job")
        dispatch = (
            TEST_DATA_PATH_OBJECT / "sower" / "dispatch-get-dbgap.json"
        ).read_text(encoding="UTF-8")
        dispatch_json = json.loads(dispatch)
        get_dbgap_input = dispatch_json.get(match_type).get("get_dbgap_input")
        logger.info(f"Dispatch input: {get_dbgap_input}")

        # clear out any existing metadata
        test_guid = dispatch_json.get(match_type).get("expected").get("test_guid")
        try:
            mds.delete(test_guid)
        except:
            logger.debug(f"Guid not present in MDS: {test_guid}")

        # dispatch the get-dbgap sower job
        loop = get_or_create_event_loop_for_thread()
        job_output = loop.run_until_complete(
            jobs.async_run_job_and_wait(
                job_name=DBGAP_METADATA_JOB, job_input=get_dbgap_input
            )
        )
        assert job_output.get("output")

        log_url, pre_signed_url = job_output.get("output").split()
        logger.info(f"Log url: {log_url}")
        logger.info(f"Pre-signed-url: {pre_signed_url}")

        # get tsv data using pre-signed url
        tsv_data = requests.get(pre_signed_url)
        logger.info(f"TSV data text = {tsv_data.text}")
        assert (
            test_guid in tsv_data.text
        ), f"TSV data does not have test guid: {test_guid}"

        # This section replicates the 'test_dispatch_ingest_metadata' test from above.
        # submit the TSV to sower
        ingest_input = {
            "URL": pre_signed_url,
            "metadata_source": "dbgap",
            "host": hostname,
        }
        logger.info(f"Dispatch input: {input}")
        job_output = loop.run_until_complete(
            jobs.async_run_job_and_wait(
                job_name=INGEST_METADATA_JOB, job_input=ingest_input
            )
        )
        assert job_output.get("output")

        # check that submitted_sample_id is in metadata.
        dbgap_guids = mds.query("dbgap=*")
        assert (
            test_guid in dbgap_guids
        ), f"dbgap guids does not contain test_guid {test_guid}"

        try:
            study_metadata = mds.get(test_guid)
            logger.info(f"Study metadata {study_metadata}")
            logger.info(f"DBGAP {study_metadata.get('dbgap')}")
        except:
            logger.error(
                f"Could not get metadata. Guid not present in MDS: {test_guid}"
            )
        assert study_metadata.get("dbgap").get(
            "submitted_sample_id"
        ) == dispatch_json.get(match_type).get("expected").get(
            "submitted_sample_id"
        ), f"Metadata for {test_guid} does not have submitted sample id."

        try:
            mds.delete(test_guid)
        except:
            logger.debug(
                f"Could not delete metadata. Guid not present in MDS: {test_guid}"
            )

    # This replicates Scenario #4 in original test (in the ingest_metadata suite).
    # This can be used for test_aggregate_mds if the aggregate commands are folded in.
    def test_create_edit_delete_study(self):
        """
        Steps:
        1. Create a metadata record and verify creation.
        2. Update the metadata record and verify updation.
        3. Delete the metadata record and verify deletion.

        """

        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        mds = Gen3Metadata(auth_provider=auth)

        study_json_files = ["study1.json", "study2.json", "study3.json"]
        """Create, edit and delete study from aggregate metadata"""
        # Identify UID field name from gitops.json
        logger.info("# Fetch UID field name from gitops.json")
        portal_config = gat.get_portal_config(pytest.namespace)
        assert portal_config is not None
        uid_field_name = (
            portal_config.get("discoveryConfig", {})
            .get("minimalFieldMapping", {})
            .get("uid", None)
        )
        assert uid_field_name is not None

        # Test data
        study_ids = []
        study_jsons = []
        for file_name in study_json_files:
            logger.info(f"# Create study json from {file_name}")
            study_id = uuid.uuid4().hex
            study_ids.append(study_id)
            study = (TEST_DATA_PATH_OBJECT / "aggregate_mds" / file_name).read_text(
                encoding="UTF-8"
            )
            study_json = json.loads(study)
            study_json["gen3_discovery"][uid_field_name] = study_id
            project_title = study_json["gen3_discovery"]["project_title"]
            assert project_title is not None
            study_jsons.append(study_json)

        logger.info("# Create metadata records")
        for i in range(len(study_ids)):
            # Try deleting the study_ids in case they exist from a previous run
            try:
                mds.delete(study_ids[i])
            except:
                logger.debug(f"Guid not present in MDS prior to create: {study_ids[i]}")
            mds.create(study_ids[i], study_jsons[i])
            # verify that study is in MDS
            submitted_guids = mds.query("gen3_discovery=*")
            logger.info(f"Test guid {study_ids[i]}")
            logger.info(f"submitted_guids: {submitted_guids}")
            # assert study_ids[i] in submitted_guids, f"Test guid {study_ids[i]} not found in MDS."
            try:
                study_metadata = mds.get(study_ids[i])
            except:
                logger.error(
                    f"Could not get metadata. Guid not present in MDS: {study_ids[i]}"
                )
            assert (
                study_metadata.get("gen3_discovery").get("project_title")
                == study_jsons[i]["gen3_discovery"]["project_title"]
            ), f"Metadata for {study_ids[i]} does not have correct project_title."

        logger.info("# Update metadata records")
        for i in range(len(study_ids)):
            project_title = study_jsons[i]["gen3_discovery"]["project_title"]
            study_jsons[i]["gen3_discovery"][
                "project_title"
            ] = f"{project_title} - Modified"
            mds.update(study_ids[i], study_jsons[i])
            try:
                study_metadata = mds.get(study_ids[i])
            except:
                logger.error(
                    f"Could not get metadata. Guid not present in MDS: {study_ids[i]}"
                )
            assert (
                study_metadata.get("gen3_discovery").get("project_title")
                == study_jsons[i]["gen3_discovery"]["project_title"]
            ), f"Metadata for {study_ids[i]} does not have correct project_title."

        logger.info("# Delete metadata records")
        for i in range(len(study_ids)):
            logger.info(f"Study to delete {study_ids[i]}")
            try:
                mds.delete(study_ids[i])
            except:
                logger.error(f"Could not delete study_id from MDS: {study_ids[i]}")
