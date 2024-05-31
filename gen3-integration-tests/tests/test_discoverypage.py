import json
import os
import pytest

from utils import logger
from uuid import uuid4

from pages import login, discovery
from utils import TEST_DATA_PATH_OBJECT, gen3_admin_tasks as gat

from services.indexd import Indexd
from services.metadataservice import MetadataService
from utils.test_execution import screenshot


@pytest.mark.workspace
@pytest.mark.mds
@pytest.mark.agg_mds
class TestDiscoveryPage(object):
    variables = {}

    @classmethod
    def setup_class(cls):
        logger.info("Setup - create uuids for did and study_id")
        cls.variables["did"] = str(uuid4())
        cls.variables["study_id"] = uuid4().hex
        cls.variables[
            "md5sum"
        ] = "694b1d13b8148756442739fa2cc37fd6"  # pragma: allowlist secret

    @classmethod
    def teardown_class(cls):
        logger.info("Tearing down - delete indexd record and study metadata")
        indexd = Indexd()
        mds = MetadataService()
        indexd.delete_files([cls.variables["did"]])
        mds.delete_metadata(cls.variables["study_id"])

    def test_study_publish_search_export(self, page):
        """
        Scenario: Publish a study, search discovery page and export to workspace
        Steps:
            1. Create indexd record
            2. Populate study metadata
            3. Run metadata-aggregate-sync
            4. Perform tag and text search on discovery page
            5. Open study in workspace
        """
        # Get uid field and study preview field from portal config
        portal_config = gat.get_portal_config(pytest.tested_env)
        uid_field_name = (
            portal_config.get("discoveryConfig", {})
            .get("minimalFieldMapping", {})
            .get("uid", None)
        )
        study_preview_field = (
            portal_config.get("discoveryConfig", {})
            .get("studyPreviewField", {})
            .get("field", None)
        )
        assert uid_field_name is not None
        assert study_preview_field is not None

        # Create indexd record
        indexd_records = {
            "test": {
                "filename": "discovery_test.csv",
                "did": self.variables["did"],
                "link": "s3://cdis-presigned-url-test/testdata/discovery_test.csv",
                "md5": self.variables["md5sum"],
                "authz": ["/programs/QA"],
                "size": 16,
            }
        }
        indexd = Indexd()
        indexd.create_files(indexd_records)

        # Create study metadata record
        mds = MetadataService()
        study = (TEST_DATA_PATH_OBJECT / "aggregate_mds" / "study1.json").read_text(
            encoding="UTF-8"
        )
        study_json = json.loads(study)
        if study_preview_field != "summary":
            study_json["gen3_discovery"][study_preview_field] = study_json[
                "gen3_discovery"
            ]["summary"]
        study_json["gen3_discovery"][uid_field_name] = self.variables["study_id"]
        study_json["gen3_discovery"]["__manifest"].append(
            {
                "md5sum": self.variables["md5sum"],
                "file_name": "discovery_test.csv",
                "file_size": 16,
                "object_id": self.variables["did"],
                "commons_url": pytest.hostname,
            }
        )
        mds.create_metadata(self.variables["study_id"], study_json)

        # Re-sync aggregate mds
        gat.run_gen3_job(pytest.namespace, "metadata-aggregate-sync")
        study_metadata = mds.get_aggregate_metadata(self.variables["study_id"])
        assert study_metadata["commons_name"] == "HEAL"

        # Navigate to discovery page
        login_page = login.LoginPage()
        login_page.go_to(page)
        login_page.login(page)
        discovery_page = discovery.DiscoveryPage()
        discovery_page.go_to(page)
        screenshot(page, "DiscoveryPage")

        # Tag search
        discovery_page.search_tag(page, "AUTOTEST Tag")
        screenshot(page, "TagSearch")
        assert discovery_page.study_found(page, self.variables["study_id"])
        screenshot(page, "StudyFound")

        # Text search by study title
        discovery_page.go_to(page)
        discovery_page.search_text(page, "AUTOTEST Title")
        screenshot(page, "TextSearchTitle")
        assert discovery_page.study_found(page, self.variables["study_id"])
        screenshot(page, "StudyFound")

        # Text search by study summary
        discovery_page.go_to(page)
        discovery_page.search_text(page, "AUTOTEST Summary")
        screenshot(page, "TextSearchSummary")
        assert discovery_page.study_found(page, self.variables["study_id"])
        screenshot(page, "StudyFound")

        # Open study in workspace
        discovery_page.open_in_workspace(page, self.variables["study_id"])
        page.wait_for_url("**/workspace", timeout=120000)
        screenshot(page, "OpenInWorkspace")
