import json
import os
import uuid
import pytest

from cdislogging import get_logger

import utils.gen3_admin_tasks as gat

from services.metadataservice import MetadataService

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class TestAggregateMDS:
    def test_expect_pass(self):
        assert 1 == 1

    def test_expect_fail(self):
        assert 1 == 2

    @pytest.mark.skip()
    def test_create_edit_delete_study(self, test_data_path):
        mds = MetadataService()
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
            study = (test_data_path / "aggregate_mds" / file_name).read_text(
                encoding="UTF-8"
            )
            study_json = json.loads(study)
            study_json["gen3_discovery"][uid_field_name] = study_id
            project_title = study_json["gen3_discovery"]["project_title"]
            assert project_title is not None
            study_jsons.append(study_json)

        # Create metadata record
        logger.info("# Create metadata records")
        for i in range(len(study_ids)):
            mds.create_metadata(study_ids[i], study_jsons[i])

        # Metadata-aggregate-sync and verify
        logger.info("# Run metadata-aggregate-sync and verify")
        gat.run_gen3_job(pytest.namespace, "metadata-aggregate-sync")
        for i in range(len(study_ids)):
            study_metadata = mds.get_aggregate_metadata(study_ids[i])
            assert study_metadata["commons_name"] == "HEAL"
            assert (
                study_metadata["project_title"]
                == study_jsons[i]["gen3_discovery"]["project_title"]
            )

        # Edit metadata record
        logger.info("# Update metadata records")
        for i in range(len(study_ids)):
            project_title = study_jsons[i]["gen3_discovery"]["project_title"]
            study_jsons[i]["gen3_discovery"][
                "project_title"
            ] = f"{project_title} - Modified"
            # metadata.update(study_id, study_json)
            mds.update_metadata(study_ids[i], study_jsons[i])

        # Metadata-aggregate-sync and verify
        logger.info("# Run metadata-aggregate-sync and verify")
        gat.run_gen3_job(pytest.namespace, "metadata-aggregate-sync")
        for i in range(len(study_ids)):
            study_metadata = mds.get_aggregate_metadata(study_ids[i])
            assert (
                study_metadata["project_title"]
                == study_jsons[i]["gen3_discovery"]["project_title"]
            )

        # Delete metadata record
        for i in range(len(study_ids)):
            mds.delete_metadata(study_ids[i])

        ####
        # metadata-aggregate-sync fails when there are 0 records in MDS
        ####
        # # Metadata-aggregate-sync and verify
        # logger.info("# Run metadata-aggregate-sync and verify")
        # gat.run_gen3_job(pytest.namespace, "metadata-aggregate-sync")
        # for i in range(len(study_ids)):
        #     response = gen3auth.curl(f"/mds/aggregate/metadata/guid/{study_ids[i]}")
        #     assert response.status_code == 404
