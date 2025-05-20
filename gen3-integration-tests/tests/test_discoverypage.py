import json
from uuid import uuid4

import pytest
from pages.discovery import DiscoveryPage
from pages.login import LoginPage
from pages.workspace import WorkspacePage
from services.indexd import Indexd
from services.metadataservice import MetadataService
from utils import TEST_DATA_PATH_OBJECT
from utils import gen3_admin_tasks as gat
from utils import logger
from utils.test_execution import screenshot


@pytest.fixture()
def page_setup(page):
    yield page
    workspace = WorkspacePage()
    if page.locator(workspace.TERMINATE_BUTTON).is_visible():
        workspace.terminate_workspace(page)
        screenshot(page, "WorkspaceTerminatedInTearDown")
    page.close()


@pytest.mark.skipif(
    "wts" not in pytest.deployed_services,
    reason="wts service is not running on this environment",
)
@pytest.mark.skipif(
    "metadata" not in pytest.deployed_services,
    reason="metadata service is not running on this environment",
)
@pytest.mark.skipif(
    "portal" not in pytest.deployed_services,
    reason="portal service is not running on this environment",
)
@pytest.mark.skipif(
    not pytest.use_agg_mdg_flag,
    reason="USE_AGG_MDS is not set or is false in manifest",
)
@pytest.mark.skipif(
    "discoveryConfig" not in gat.get_portal_config().keys(),
    reason="discoveryConfig in not in portal config",
)
@pytest.mark.workspace
@pytest.mark.mds
@pytest.mark.agg_mds
@pytest.mark.wts
@pytest.mark.portal
@pytest.mark.skipif(
    pytest.skip_portal_tests,
    reason="Skipping based on portal version",
)
class TestDiscoveryPage(object):
    variables = {}

    @classmethod
    def setup_class(cls):
        logger.info("Setup - create uuids for did and study_id")
        cls.variables["did"] = str(uuid4())
        cls.variables["study_id"] = uuid4().hex
        cls.variables["md5sum"] = (
            "694b1d13b8148756442739fa2cc37fd6"  # pragma: allowlist secret
        )

    @classmethod
    def teardown_class(cls):
        logger.info(
            "Tearing down - delete indexd record and study metadata, and terminate workspace"
        )
        indexd = Indexd()
        mds = MetadataService()
        indexd.delete_records([cls.variables["did"]])
        mds.delete_metadata(cls.variables["study_id"])

    def test_study_publish_search_export(self, page_setup):
        """
        Scenario: Publish a study, search discovery page and export to workspace
        Steps:
            1. Create indexd record
            2. Populate study metadata
            3. Run metadata-aggregate-sync
            4. Perform tag and text search on discovery page
            5. Open study in workspace
            6. Open a python notebook
            7. Run a gen3 command
            8. Terminate workspace
        """
        # Get uid field and study preview field from portal config
        portal_config = gat.get_portal_config()
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
                "file_name": "discovery_test.csv",
                "did": self.variables["did"],
                "urls": ["s3://cdis-presigned-url-test/testdata/discovery_test.csv"],
                "hashes": {"md5": self.variables["md5sum"]},
                "authz": ["/programs/QA"],
                "size": 16,
            }
        }
        indexd = Indexd()
        indexd.create_records(indexd_records)

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
        gat.run_gen3_job("metadata-aggregate-sync", test_env_namespace=pytest.namespace)
        study_metadata = mds.get_aggregate_metadata(self.variables["study_id"])[
            "gen3_discovery"
        ]
        assert study_metadata["commons_name"] == "HEAL"

        # Navigate to discovery page
        login_page = LoginPage()
        login_page.go_to(page_setup)
        login_page.login(page_setup)
        discovery_page = DiscoveryPage()
        discovery_page.go_to(page_setup)
        screenshot(page_setup, "DiscoveryPage")

        # Tag search
        discovery_page.search_tag(page_setup, "AUTOTEST Tag")
        screenshot(page_setup, "TagSearch")
        assert discovery_page.study_found(page_setup, self.variables["study_id"])
        screenshot(page_setup, "StudyFound")

        # Text search by study title
        discovery_page.go_to(page_setup)
        discovery_page.search_text(page_setup, "AUTOTEST Title")
        screenshot(page_setup, "TextSearchTitle")
        assert discovery_page.study_found(page_setup, self.variables["study_id"])
        screenshot(page_setup, "StudyFound")

        # Text search by study summary
        discovery_page.go_to(page_setup)
        discovery_page.search_text(page_setup, "AUTOTEST Summary")
        screenshot(page_setup, "TextSearchSummary")
        assert discovery_page.study_found(page_setup, self.variables["study_id"])
        screenshot(page_setup, "StudyFound")

        # Open study in workspace
        discovery_page.open_in_workspace(page_setup, self.variables["study_id"])
        workspace_page = WorkspacePage()
        workspace_page.assert_page_loaded(page_setup)
        workspace_page.launch_workspace(
            page_setup, "(Tutorial) Bacpac Synthetic Data Analysis Notebook"
        )
        screenshot(page_setup, "WorkspaceLaunched")

        # Open Python notebook and run gen3 commands
        workspace_page.open_python_notebook(page_setup)
        command = "!pip install -U gen3==4.24.1"  # TODO: Fix the workspace image in jenkins envs, use jupyterlab
        logger.info(f"Running in jupyter notebook: {command}")
        result = workspace_page.run_command_in_notebook(page_setup, command)
        command = f"!gen3 drs-pull object {self.variables['did']}"
        logger.info(f"Running in jupyter notebook: {command}")
        result = workspace_page.run_command_in_notebook(page_setup, command)
        logger.info(f"Result: {result}")

        # Terminate workspace
        workspace_page.terminate_workspace(page_setup)
        screenshot(page_setup, "WorkspaceTerminated")
