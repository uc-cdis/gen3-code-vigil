import json
import os
import uuid
import pytest
import requests

from cdislogging import get_logger
from gen3.auth import Gen3Auth
from gen3.metadata import Gen3Metadata
from pathlib import Path

import utils.gen3_admin_tasks as gat

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


class TestAggregateMDS:
    test_data_path = (
        f"{Path(__file__).resolve().parent.parent.parent}/test_data/aggregate_mds"
    )
    study_json_files = ["study1.json", "study2.json", "study3.json"]

    def test_create_edit_delete_study(self):
        """Create, edit and delete study from aggregate metadata"""
        # Identify UID field name from gitops.json
        logger.info("# Fetch UID field name from gitops.json")
        portal_config = gat.get_portal_config(os.getenv("NAMESPACE"))
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
        for file_name in self.study_json_files:
            logger.info(f"# Create study json from {file_name}")
            study_id = uuid.uuid4().hex
            study_ids.append(study_id)
            with open(f"{self.test_data_path}/{file_name}") as f:
                study_json = json.load(f)
            study_json["gen3_discovery"][uid_field_name] = study_id
            project_title = study_json["gen3_discovery"]["project_title"]
            assert project_title is not None
            study_jsons.append(study_json)

        # Create metadata record
        logger.info("# Create metadata records")
        gen3auth = Gen3Auth(refresh_file=os.getenv("NAMESPACE"))
        auth_header = {
            "Accept": "application/json",
            "Authorization": f"bearer {gen3auth.get_access_token()}",
            "Content-Type": "application/json",
        }
        for i in range(len(study_ids)):
            response = requests.post(
                f"{os.getenv('HOSTNAME')}/mds/metadata/{study_ids[i]}",
                data=json.dumps(study_jsons[i]),
                headers=auth_header,
            )
            assert response.status_code == 201

        # Metadata-aggregate-sync and verify
        logger.info("# Run metadata-aggregate-sync and verify")
        gat.run_gen3_job(os.getenv("NAMESPACE"), "metadata-aggregate-sync")
        for i in range(len(study_ids)):
            response = gen3auth.curl(f"/mds/aggregate/metadata/guid/{study_ids[i]}")
            assert response.status_code == 200
            study_metadata = response.json()["gen3_discovery"]
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
            response = requests.put(
                f'{os.getenv("HOSTNAME")}/mds/metadata/{study_ids[i]}',
                data=json.dumps(study_jsons[i]),
                headers=auth_header,
            )
            assert response.status_code == 200

        # Metadata-aggregate-sync and verify
        logger.info("# Run metadata-aggregate-sync and verify")
        gat.run_gen3_job(os.getenv("NAMESPACE"), "metadata-aggregate-sync")
        for i in range(len(study_ids)):
            response = gen3auth.curl(f"/mds/aggregate/metadata/guid/{study_ids[i]}")
            assert response.status_code == 200
            study_metadata = response.json()["gen3_discovery"]
            assert (
                study_metadata["project_title"]
                == study_jsons[i]["gen3_discovery"]["project_title"]
            )

        # Delete metadata record
        for i in range(len(study_ids)):
            response = requests.delete(
                f'{os.getenv("HOSTNAME")}/mds/metadata/{study_ids[i]}',
                headers=auth_header,
            )
            assert response.status_code == 200

        # # Metadata-aggregate-sync and verify
        # logger.info("# Run metadata-aggregate-sync and verify")
        # gat.run_gen3_job(os.getenv("NAMESPACE"), "metadata-aggregate-sync")
        # for i in range(len(study_ids)):
        #     response = gen3auth.curl(f"/mds/aggregate/metadata/guid/{study_ids[i]}")
        #     assert response.status_code == 404
