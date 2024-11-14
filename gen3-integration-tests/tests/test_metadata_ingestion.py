import asyncio
import uuid

import nest_asyncio
import pytest
from gen3.auth import Gen3Auth
from gen3.jobs import INGEST_METADATA_JOB, Gen3Jobs
from services.metadataservice import MetadataService
from utils import logger

nest_asyncio.apply()


@pytest.mark.mds
@pytest.mark.sower
class TestMetadataIngestion:
    variables = {}
    variables["UNIQUE_NUM"] = uuid.uuid1().time
    variables["TSV_URL"] = (
        "https://cdis-presigned-url-test.s3.amazonaws.com/test-study-subject-id.tsv"
    )
    variables["STUDY_ID"] = "95a41871-222c-48ae-8004-63f4ed1f0691"
    variables["SRA_SAMPLE_ID"] = "SRS1361261"

    @classmethod
    def setup_class(cls):
        logger.info("Clean up mds records before testing")
        mds = MetadataService()
        try:
            mds.delete_metadata(study_id=cls.variables["STUDY_ID"])
        except Exception:
            logger.info("Study was not found. Ignore initial cleanup")

    @classmethod
    def teardown_class(cls):
        logger.info("Clean up mds records after testing")
        mds = MetadataService()
        mds.delete_metadata(study_id=cls.variables["STUDY_ID"])

    def test_metadata_ingestion_with_tsv_file(self):
        """
        Scenario: Dispatch ingest-metadata-manifest sower job with simple tsv and verify metadata ingestion
        Steps:
            1. Dispatch sower job ingest-metadata-manifest with a simple tsv
            2. Verify creation of mds record
        """
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"])
        jobs = Gen3Jobs(auth)
        job_input = {"URL": self.variables["TSV_URL"], "metadata_source": "dbgap"}
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            jobs.async_run_job_and_wait(
                job_name=INGEST_METADATA_JOB, job_input=job_input
            )
        )

        mds = MetadataService()
        study_json = mds.get_metadata(study_id=self.variables["STUDY_ID"])
        assert study_json["dbgap"]["sra_sample_id"] == self.variables["SRA_SAMPLE_ID"]
