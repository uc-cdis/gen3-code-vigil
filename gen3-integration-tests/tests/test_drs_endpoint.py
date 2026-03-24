"""
DRS Endpoint
"""

import os
from uuid import uuid4

import pytest
import requests
from cdislogging import get_logger
from gen3.auth import Gen3Auth
from packaging.version import Version
from services.drs import Drs
from services.fence import Fence
from services.indexd import Indexd

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))

indexd_files = {
    "allowed": {
        "file_name": "test_valid",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["jenkins"],
        "size": 9,
    },
    "not_allowed": {
        "file_name": "test_not_allowed",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["acct"],
        "size": 9,
    },
    "invalid_protocol": {
        "file_name": "test_invalid_protocol",
        "urls": ["s2://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["jenkins"],
        "size": 9,
    },
}


@pytest.mark.skipif(
    "fence" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.fence
@pytest.mark.drs
class TestDrsEndpoints:
    @classmethod
    def setup_class(cls):
        cls.indexd = Indexd()
        cls.drs = Drs()
        cls.fence = Fence()
        cls.variables = {}
        cls.variables["created_indexd_dids"] = []
        # Adding indexd files
        for key, val in indexd_files.items():
            indexd_record = cls.indexd.create_records(records={key: val})
            cls.variables["created_indexd_dids"].append(indexd_record[0]["did"])

    @classmethod
    def teardown_class(cls):
        # Removing test indexd records
        cls.indexd.delete_records(cls.variables["created_indexd_dids"])

    def test_get_drs_object(self):
        """
        Scenario: get drs object
        Steps:
            1. Get the drs object for indexd record (allowed).
            2. Get the drs object and compare the records are same.
        """
        drs_record = self.drs.get_drs_object(file=indexd_files["allowed"])
        res = self.drs.get_drs_object(drs_record.json())
        assert (
            drs_record.json() == res.json()
        ), f"Expected same values but got different.\ndrs_record: {drs_record}\nResponse: {res}"

    def test_get_drs_no_record_found(self):
        """
        Scenario: get drs no record found
        Steps:
            1. Get the drs object for indexd record (not_allowed).
            2. Get the drs object usign the response object in step 1. Drs object shouldn't be returned.
        """
        drs_record = self.drs.get_drs_object(file=indexd_files["not_allowed"])
        res = self.drs.get_drs_object(drs_record)
        assert (
            res.status_code == 404
        ), f"Expected status code 404, but got {res.status_code}"
        logger.info(res.content)

    def test_get_drs_presigned_url(self):
        """
        Scenario: get drs presigned-url
        Steps:
            1. Get the drs presgined url for indexd record (allowed).
            2. Validate the content of the file checkout.
        """
        signed_url_res = self.drs.get_drs_signed_url(file=indexd_files["allowed"])
        self.fence.check_file_equals(
            signed_url_res=signed_url_res.json(),
            file_content="Hi Zac!\ncdis-data-client uploaded this!\n",
        )

    def test_get_drs_invalid_access_id(self):
        """
        Scenario: get drs invalid access id
        Steps:
            1. Get the drs presgined url for indexd record (invalid_protocol).
            2. Validate the response is 400 since the s2 protocol used here is not supported.
        """
        expected_msg = "The specified protocol s2 is not supported"
        signed_url_res = self.drs.get_drs_signed_url(
            file=indexd_files["invalid_protocol"]
        )
        # The specified protocol s2 is not supported (part of the signed_url_res.content) so status is 400
        assert (
            signed_url_res.status_code == 400
        ), f"Expected status 400 but got {signed_url_res.status_code}"
        assert (
            expected_msg in signed_url_res.content.decode()
        ), f"{expected_msg} not found in {signed_url_res.content.decode()}"


# Separate indexd_files for DRS 1.5 tests
# Records include DRS 1.5 fields
drs_15_indexd_files = {
    # S3 record with region and available=true
    "s3_available": {
        "file_name": "test_s3_available",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["jenkins"],
        "authz": ["/programs/jenkins"],
        "size": 9,
        "available": True,
        "urls_metadata": {
            "s3://cdis-presigned-url-test/testdata": {"region": "us-east-1"}
        },
    },
    # S3 record with available=false
    "s3_unavailable": {
        "file_name": "test_s3_cold_storage",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["jenkins"],
        "authz": ["/programs/jenkins"],
        "size": 9,
        "available": False,
    },
    # GCS record for cloud testing
    "gs_record": {
        "file_name": "test_gs_record",
        "urls": ["gs://some-gs-bucket/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["jenkins"],
        "authz": ["/programs/jenkins"],
        "size": 9,
        "available": True,
    },
    # S3 record without available (should default to true)
    "default_available": {
        "file_name": "test_default_available",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["jenkins"],
        "authz": ["/programs/jenkins"],
        "size": 9,
    },
    # Unknown protocol "s2"
    "unknown_protocol": {
        "file_name": "test_unknown_protocol_15",
        "urls": ["s2://some-bucket/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["jenkins"],
        "authz": ["/programs/jenkins"],
        "size": 9,
    },
    # Open access record
    "open_access": {
        "file_name": "test_open_access",
        "urls": ["s3://cdis-presigned-url-test/testdata"],
        "hashes": {"md5": "73d643ec3f4beb9020eef0beed440ad0"},
        "acl": ["*"],
        "authz": ["/open"],
        "size": 9,
    },
}


@pytest.mark.skipif(
    "fence" not in pytest.deployed_services or "indexd" not in pytest.deployed_services,
    reason="DRS 1.5 tests require both fence and indexd",
)
@pytest.mark.fence
@pytest.mark.drs
class TestDrsMetadata:
    """DRS 1.5 metadata field tests"""

    @classmethod
    def setup_class(cls):
        cls.drs = Drs()
        cls.indexd = Indexd()
        cls.fence = Fence()
        cls.variables = {"created_indexd_dids": []}

        # skip all these tests if DRS < 1.5
        try:
            resp = cls.drs.get_service_info()
            if resp.status_code == 200:
                version_str = resp.json().get("type", {}).get("version", "1.2")
            else:
                version_str = "1.2"
        except Exception:
            version_str = "1.2"
        if Version(version_str) < Version("1.5"):
            pytest.skip("DRS 1.5 not deployed on this environment")

        # Create DRS 1.5 test records
        auth = Gen3Auth(
            refresh_token=pytest.api_keys["indexing_account"],
            endpoint=pytest.root_url,
        )
        access_token = auth.get_access_token()
        headers = {
            "Authorization": f"bearer {access_token}",
            "Content-Type": "application/json",
        }
        for key, val in drs_15_indexd_files.items():
            val.setdefault("did", str(uuid4()))
            resp = requests.post(
                f"{pytest.root_url}/index/index/",
                json=val,
                headers=headers,
            )
            assert resp.status_code == 200, (
                f"Failed to create indexd record '{key}': "
                f"{resp.status_code} {resp.text}"
            )
            cls.variables["created_indexd_dids"].append(resp.json()["did"])

    @classmethod
    def teardown_class(cls):
        if hasattr(cls, "variables") and cls.variables.get("created_indexd_dids"):
            cls.indexd.delete_records(cls.variables["created_indexd_dids"])

    def test_drs_object_cloud_derivation(self):
        """
        Scenario: Verify cloud field is correctly derived from URL protocols
        Steps:
            1. Get DRS object for S3 record, verify cloud is 'aws'.
            2. Get DRS object for GCS record, verify cloud is 'gcp'.
            3. Get DRS object for unknown protocol (s2://), verify cloud is null.
        """
        # S3 -> aws
        s3_obj = self.drs.get_drs_object(file=drs_15_indexd_files["s3_available"])
        assert s3_obj.status_code == 200, f"Expected 200, got {s3_obj.status_code}"
        for method in s3_obj.json().get("access_methods", []):
            assert (
                method.get("cloud") == "aws"
            ), f"Expected cloud='aws' for s3:// URL, got '{method.get('cloud')}'"
        # GS -> gcp
        gs_obj = self.drs.get_drs_object(file=drs_15_indexd_files["gs_record"])
        assert gs_obj.status_code == 200
        for method in gs_obj.json().get("access_methods", []):
            assert (
                method.get("cloud") == "gcp"
            ), f"Expected cloud='gcp' for gs:// URL, got '{method.get('cloud')}'"
        # Unknown protocol -> null
        unk_obj = self.drs.get_drs_object(file=drs_15_indexd_files["unknown_protocol"])
        assert unk_obj.status_code == 200
        for method in unk_obj.json().get("access_methods", []):
            assert method.get("cloud") is None, (
                f"Expected cloud=null for unknown protocol, "
                f"got '{method.get('cloud')}'"
            )

    def test_drs_object_region_value(self):
        """
        Scenario: Verify region field is present and matches urls_metadata value
        Steps:
            1. Get DRS object for S3 record with urls_metadata region 'us-east-1'.
            2. Verify each access method has a non-empty region equal to 'us-east-1'.
        """
        obj = self.drs.get_drs_object(file=drs_15_indexd_files["s3_available"])
        assert obj.status_code == 200
        for method in obj.json().get("access_methods", []):
            assert "region" in method, "access_method missing 'region' field"
            assert (
                method["region"] == "us-east-1"
            ), f"Expected region='us-east-1', got '{method.get('region')}'"

    def test_drs_object_region_from_bucket_cache(self):
        """
        Scenario: Verify region from Fence bucket-to-region cache
        Steps:
            1. Query Fence GET /data/buckets for bucket region info.
            2. Get DRS object for record without urls_metadata region.
            3. Verify region matches Fence bucket config.
        NOTE:
            To pass this, add cdis-presigned-url-test to fence config with region: us-east-1
        """
        auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"],
            endpoint=pytest.root_url,
        )
        buckets_resp = auth.curl(path="/data/buckets")
        if buckets_resp.status_code != 200:
            pytest.skip("Fence /data/buckets endpoint not available")

        buckets = buckets_resp.json()
        expected_region = None
        for bucket_name, info in buckets.items():
            if "cdis-presigned-url-test" in bucket_name:
                expected_region = info.get("region")
                break
        if not expected_region:
            pytest.skip("cdis-presigned-url-test bucket not in Fence bucket config")

        obj = self.drs.get_drs_object(file=drs_15_indexd_files["default_available"])
        assert obj.status_code == 200
        for method in obj.json().get("access_methods", []):
            assert method.get("region") == expected_region, (
                f"Expected region='{expected_region}' from bucket cache, "
                f"got '{method.get('region')}'"
            )

    def test_drs_object_available_true_by_default(self):
        """
        Scenario: Verify available defaults to true when not explicitly set
        Steps:
            1. Get DRS object for record created without 'available' field.
            2. Verify each access method has available=true.
        """
        obj = self.drs.get_drs_object(file=drs_15_indexd_files["default_available"])
        assert obj.status_code == 200
        for method in obj.json().get("access_methods", []):
            assert method.get("available") is True, (
                f"Expected available=true by default, " f"got {method.get('available')}"
            )

    def test_drs_object_available_explicit(self):
        """
        Scenario: Verify available field reflects explicit true and false values
        Steps:
            1. Get DRS object for record with available=true, verify true.
            2. Get DRS object for record with available=false, verify false.
        """
        obj = self.drs.get_drs_object(file=drs_15_indexd_files["s3_available"])
        assert obj.status_code == 200
        for method in obj.json().get("access_methods", []):
            assert (
                method.get("available") is True
            ), f"Expected available=true, got {method.get('available')}"

        obj = self.drs.get_drs_object(file=drs_15_indexd_files["s3_unavailable"])
        assert obj.status_code == 200
        for method in obj.json().get("access_methods", []):
            assert (
                method.get("available") is False
            ), f"Expected available=false, got {method.get('available')}"

    def test_drs_authorizations_protected_record(self):
        """
        Scenario: Verify authorizations for a protected record include bearer auth
        Steps:
            1. Get DRS object for record with authz path.
            2. Verify each access method has 'authorizations' with 'supported_types'.
            3. Verify supported_types includes 'BearerAuth'.
            4. Verify bearer_auth_issuers contains the commons issuer URL.
        """
        expected_issuer = f"{pytest.root_url}/user"
        obj = self.drs.get_drs_object(file=drs_15_indexd_files["default_available"])
        assert obj.status_code == 200
        for method in obj.json().get("access_methods", []):
            assert (
                "authorizations" in method
            ), "access_method missing 'authorizations' for protected record"
            authz = method["authorizations"]
            assert (
                "supported_types" in authz
            ), "authorizations missing 'supported_types'"
            supported = authz.get("supported_types", [])
            assert (
                "BearerAuth" in supported
            ), f"Expected 'BearerAuth' in supported_types, got {supported}"
            issuers = authz.get("bearer_auth_issuers", [])
            assert expected_issuer in issuers, (
                f"Expected '{expected_issuer}' in bearer_auth_issuers, "
                f"got {issuers}"
            )

    def test_drs_authorizations_open_data(self):
        """
        Scenario: Verify open data has no auth required
        Steps:
            1. Get DRS object for record with /open authz path.
            2. Verify supported_types is ['None'] or authorizations is absent.
        """
        obj = self.drs.get_drs_object(file=drs_15_indexd_files["open_access"])
        assert obj.status_code == 200
        for method in obj.json().get("access_methods", []):
            authz = method.get("authorizations")
            if authz is not None:
                supported = authz.get("supported_types", [])
                assert supported == ["None"], (
                    f"Expected supported_types=['None'] for open data, "
                    f"got {supported}"
                )

    def test_options_object_authorizations(self):
        """
        Scenario: Verify OPTIONS endpoint returns correct authorization info
        Steps:
            1. Send OPTIONS request for a protected DRS object.
            2. Verify response contains supported_types, drs_object_id,
               and non-empty bearer_auth_issuers.
        """
        resp = self.drs.get_drs_object_authorizations(
            file=drs_15_indexd_files["s3_available"]
        )
        assert (
            resp.status_code == 200
        ), f"Expected 200 from OPTIONS, got {resp.status_code}"
        data = resp.json()
        assert "supported_types" in data, "OPTIONS response missing 'supported_types'"
        assert "drs_object_id" in data, "OPTIONS response missing 'drs_object_id'"
        expected_did = drs_15_indexd_files["s3_available"]["did"]
        assert data["drs_object_id"] == expected_did, (
            f"Expected drs_object_id='{expected_did}', "
            f"got '{data['drs_object_id']}'"
        )
        assert (
            "bearer_auth_issuers" in data
        ), "OPTIONS response missing 'bearer_auth_issuers'"
        assert (
            len(data["bearer_auth_issuers"]) > 0
        ), "bearer_auth_issuers should not be empty for protected record"

    def test_options_object_not_found(self):
        """
        Scenario: Verify OPTIONS returns 404 for non-existent object
        Steps:
            1. Send OPTIONS request for a non-existent DRS object ID.
            2. Verify response status is 404.
        """
        fake_file = {"did": str(uuid4())}
        resp = self.drs.get_drs_object_authorizations(file=fake_file)
        assert (
            resp.status_code == 404
        ), f"Expected 404 for non-existent object, got {resp.status_code}"

    def test_drs_object_schema_completeness(self):
        """
        Scenario: Validate complete DRS 1.5 object response schema
        Steps:
            1. Get DRS object for a fully-configured record.
            2. Verify all required DRS fields and 1.5 AccessMethod fields.
        """
        obj = self.drs.get_drs_object(file=drs_15_indexd_files["s3_available"])
        assert obj.status_code == 200
        data = obj.json()

        # Required DRS object fields
        for field in ["id", "self_uri", "size", "checksums", "access_methods"]:
            assert field in data, f"DRS object missing required field '{field}'"

        assert (
            isinstance(data["checksums"], list) and len(data["checksums"]) > 0
        ), "checksums must be a non-empty list"
        assert (
            isinstance(data["access_methods"], list) and len(data["access_methods"]) > 0
        ), "access_methods must be a non-empty list"

        # DRS 1.5 AccessMethod from spec
        valid_types = [
            "s3",
            "gs",
            "ftp",
            "gsiftp",
            "globus",
            "htsget",
            "https",
            "file",
        ]
        for method in data["access_methods"]:
            assert "type" in method, "access_method missing 'type'"
            assert (
                method["type"] in valid_types
            ), f"Unexpected access_method type: {method['type']}"
            assert (
                "access_id" in method or "access_url" in method
            ), "access_method must have 'access_id' or 'access_url'"
            assert "cloud" in method, "access_method missing 'cloud'"
            assert "region" in method, "access_method missing 'region'"
            assert "available" in method, "access_method missing 'available'"
            assert isinstance(
                method["available"], bool
            ), f"'available' must be boolean, got {type(method['available'])}"
            assert "authorizations" in method, "access_method missing 'authorizations'"
            authz = method["authorizations"]
            assert (
                "supported_types" in authz
            ), "authorizations missing 'supported_types'"


@pytest.mark.skipif(
    "fence" not in pytest.deployed_services or "indexd" not in pytest.deployed_services,
    reason="DRS bulk endpoint tests require both fence and indexd",
)
@pytest.mark.fence
@pytest.mark.drs
class TestDrsBulkEndpoints:
    """DRS 1.4/1.5 bulk endpoint tests."""

    @classmethod
    def setup_class(cls):
        cls.drs = Drs()
        cls.indexd = Indexd()
        cls.variables = {"created_indexd_dids": []}

        # bulk endpoints require DRS >= 1.4
        try:
            resp = cls.drs.get_service_info()
            if resp.status_code == 200:
                cls.service_info = resp.json()
                version_str = cls.service_info.get("type", {}).get("version", "1.2")
            else:
                version_str = "1.2"
                cls.service_info = {}
        except Exception:
            version_str = "1.2"
            cls.service_info = {}
        if Version(version_str) < Version("1.4"):
            pytest.skip("DRS bulk endpoints not deployed (requires >= 1.4)")

        cls.max_bulk = cls.service_info.get("drs", {}).get(
            "maxBulkRequestLength",
            cls.service_info.get("maxBulkRequestLength", 100),
        )

        # Create DRS 1.5 test records
        auth = Gen3Auth(
            refresh_token=pytest.api_keys["indexing_account"],
            endpoint=pytest.root_url,
        )
        access_token = auth.get_access_token()
        headers = {
            "Authorization": f"bearer {access_token}",
            "Content-Type": "application/json",
        }
        for key, val in drs_15_indexd_files.items():
            val.setdefault("did", str(uuid4()))
            resp = requests.post(
                f"{pytest.root_url}/index/index/",
                json=val,
                headers=headers,
            )
            assert resp.status_code == 200, (
                f"Failed to create indexd record '{key}': "
                f"{resp.status_code} {resp.text}"
            )
            cls.variables["created_indexd_dids"].append(resp.json()["did"])

    @classmethod
    def teardown_class(cls):
        if hasattr(cls, "variables") and cls.variables.get("created_indexd_dids"):
            cls.indexd.delete_records(cls.variables["created_indexd_dids"])

    def test_bulk_drs_objects_include_metadata(self):
        """
        Scenario: Verify bulk DRS objects include DRS 1.5 metadata fields
        Steps:
            1. POST /objects with multiple valid GUIDs.
            2. Verify each resolved DrsObject has cloud, region, available,
               and authorizations on every access method.
        """
        object_ids = [
            drs_15_indexd_files["s3_available"]["did"],
            drs_15_indexd_files["gs_record"]["did"],
            drs_15_indexd_files["default_available"]["did"],
        ]
        resp = self.drs.get_bulk_drs_objects(object_ids=object_ids)
        assert (
            resp.status_code == 200
        ), f"Expected 200 from bulk objects, got {resp.status_code}"
        data = resp.json()

        summary = data.get("summary", {})
        assert summary.get("requested") == len(object_ids), (
            f"Expected summary.requested={len(object_ids)}, "
            f"got {summary.get('requested')}"
        )
        assert summary.get("resolved") == len(
            object_ids
        ), f"Expected all objects resolved, got resolved={summary.get('resolved')}"

        resolved = data.get("resolved_drs_object", [])
        assert len(resolved) == len(
            object_ids
        ), f"Expected {len(object_ids)} resolved objects, got {len(resolved)}"

        for drs_obj in resolved:
            assert (
                "access_methods" in drs_obj
            ), f"DrsObject {drs_obj.get('id')} missing access_methods"
            for method in drs_obj["access_methods"]:
                assert (
                    "cloud" in method
                ), f"access_method missing 'cloud' in object {drs_obj.get('id')}"
                assert (
                    "available" in method
                ), f"access_method missing 'available' in object {drs_obj.get('id')}"
                assert "authorizations" in method, (
                    f"access_method missing 'authorizations' in object "
                    f"{drs_obj.get('id')}"
                )

    def test_bulk_drs_objects_partial_resolution(self):
        """
        Scenario: Verify partial resolution with mix of valid and invalid GUIDs
        Steps:
            1. POST /objects with valid GUIDs and a non-existent GUID.
            2. Verify summary.resolved + summary.unresolved == summary.requested.
            3. Verify unresolved list contains the invalid GUID.
        """
        valid_id = drs_15_indexd_files["s3_available"]["did"]
        fake_id = str(uuid4())
        object_ids = [valid_id, fake_id]

        resp = self.drs.get_bulk_drs_objects(object_ids=object_ids)
        assert (
            resp.status_code == 200
        ), f"Expected 200 from bulk objects, got {resp.status_code}"
        data = resp.json()

        summary = data.get("summary", {})
        assert (
            summary.get("requested") == 2
        ), f"Expected summary.requested=2, got {summary.get('requested')}"
        assert summary.get("resolved", 0) + summary.get("unresolved", 0) == 2, (
            f"resolved ({summary.get('resolved')}) + "
            f"unresolved ({summary.get('unresolved')}) != requested (2)"
        )
        assert (
            summary.get("resolved") == 1
        ), f"Expected 1 resolved, got {summary.get('resolved')}"
        assert (
            summary.get("unresolved") == 1
        ), f"Expected 1 unresolved, got {summary.get('unresolved')}"

        # Verify the fake ID appears in the unresolved list
        unresolved_ids = []
        for entry in data.get("unresolved_drs_objects", []):
            unresolved_ids.extend(entry.get("object_ids", []))
        assert (
            fake_id in unresolved_ids
        ), f"Expected '{fake_id}' in unresolved object IDs, got {unresolved_ids}"

    def test_bulk_drs_objects_request_too_large(self):
        """
        Scenario: Verify 413 when bulk request exceeds maxBulkRequestLength
        Steps:
            1. Get maxBulkRequestLength from service-info.
            2. POST /objects with more GUIDs than the limit.
            3. Verify response status is 413.
        """
        oversized_ids = [str(uuid4()) for _ in range(self.max_bulk + 1)]
        resp = self.drs.get_bulk_drs_objects(object_ids=oversized_ids)
        assert resp.status_code == 413, (
            f"Expected 413 for oversized bulk request "
            f"({self.max_bulk + 1} IDs, limit {self.max_bulk}), "
            f"got {resp.status_code}"
        )

    def test_bulk_authorizations_returns_per_object_auth(self):
        """
        Scenario: Verify bulk OPTIONS returns per-object authorization info
        Steps:
            1. OPTIONS /objects with multiple valid GUIDs.
            2. Verify each resolved entry has drs_object_id and supported_types.
        """
        object_ids = [
            drs_15_indexd_files["s3_available"]["did"],
            drs_15_indexd_files["default_available"]["did"],
        ]
        resp = self.drs.get_bulk_object_authorizations(object_ids=object_ids)
        assert (
            resp.status_code == 200
        ), f"Expected 200 from bulk OPTIONS, got {resp.status_code}"
        data = resp.json()

        summary = data.get("summary", {})
        assert summary.get("requested") == len(object_ids), (
            f"Expected summary.requested={len(object_ids)}, "
            f"got {summary.get('requested')}"
        )

        resolved = data.get("resolved_drs_object", [])
        assert len(resolved) == len(
            object_ids
        ), f"Expected {len(object_ids)} resolved auth entries, got {len(resolved)}"

        for auth_entry in resolved:
            assert (
                "drs_object_id" in auth_entry
            ), "Bulk auth entry missing 'drs_object_id'"
            assert "supported_types" in auth_entry, (
                f"Bulk auth entry for '{auth_entry.get('drs_object_id')}' "
                f"missing 'supported_types'"
            )

    def test_bulk_authorizations_mixed_auth_types(self):
        """
        Scenario: Verify bulk OPTIONS returns different auth for different authz paths
        Steps:
            1. OPTIONS /objects with a protected GUID and an open-access GUID.
            2. Verify protected record has BearerAuth in supported_types.
            3. Verify open-access record has 'None' in supported_types.
        """
        protected_id = drs_15_indexd_files["s3_available"]["did"]
        open_id = drs_15_indexd_files["open_access"]["did"]
        object_ids = [protected_id, open_id]

        resp = self.drs.get_bulk_object_authorizations(object_ids=object_ids)
        assert (
            resp.status_code == 200
        ), f"Expected 200 from bulk OPTIONS, got {resp.status_code}"
        data = resp.json()

        resolved = data.get("resolved_drs_object", [])

        # Build a lookup by drs_object_id
        auth_by_id = {
            entry["drs_object_id"]: entry
            for entry in resolved
            if "drs_object_id" in entry
        }

        # Protected record should have BearerAuth
        assert (
            protected_id in auth_by_id
        ), f"Protected record '{protected_id}' not found in resolved auth entries"
        protected_types = auth_by_id[protected_id].get("supported_types", [])
        assert (
            "BearerAuth" in protected_types
        ), f"Expected 'BearerAuth' for protected record, got {protected_types}"

        # Open-access record should have 'None'
        assert (
            open_id in auth_by_id
        ), f"Open-access record '{open_id}' not found in resolved auth entries"
        open_types = auth_by_id[open_id].get("supported_types", [])
        assert (
            "None" in open_types
        ), f"Expected 'None' for open-access record, got {open_types}"

    def test_bulk_authorizations_request_too_large(self):
        """
        Scenario: Verify 413 when bulk OPTIONS exceeds maxBulkRequestLength
        Steps:
            1. OPTIONS /objects with more GUIDs than the limit.
            2. Verify response status is 413.
        """
        oversized_ids = [str(uuid4()) for _ in range(self.max_bulk + 1)]
        resp = self.drs.get_bulk_object_authorizations(object_ids=oversized_ids)
        assert resp.status_code == 413, (
            f"Expected 413 for oversized bulk OPTIONS "
            f"({self.max_bulk + 1} IDs, limit {self.max_bulk}), "
            f"got {resp.status_code}"
        )

    def test_bulk_signed_urls_success(self):
        """
        Scenario: Verify bulk presigned URL generation for authorized GUIDs
        Steps:
            1. Get DRS objects for authorized records to discover access IDs.
            2. POST /objects/access with the object_id/access_id pairs.
            3. Verify each resolved entry has a 'url' field.
        """
        # Get access IDs from the DRS objects
        s3_obj = self.drs.get_drs_object(file=drs_15_indexd_files["s3_available"])
        assert s3_obj.status_code == 200
        s3_methods = s3_obj.json().get("access_methods", [])
        assert len(s3_methods) > 0, "s3_available has no access methods"

        default_obj = self.drs.get_drs_object(
            file=drs_15_indexd_files["default_available"]
        )
        assert default_obj.status_code == 200
        default_methods = default_obj.json().get("access_methods", [])
        assert len(default_methods) > 0, "default_available has no access methods"

        bulk_access_ids = [
            {
                "bulk_object_id": drs_15_indexd_files["s3_available"]["did"],
                "bulk_access_ids": [s3_methods[0]["access_id"]],
            },
            {
                "bulk_object_id": drs_15_indexd_files["default_available"]["did"],
                "bulk_access_ids": [default_methods[0]["access_id"]],
            },
        ]

        resp = self.drs.get_bulk_signed_urls(bulk_access_ids=bulk_access_ids)
        assert (
            resp.status_code == 200
        ), f"Expected 200 from bulk signed URLs, got {resp.status_code}"
        data = resp.json()

        summary = data.get("summary", {})
        assert (
            summary.get("requested") == 2
        ), f"Expected summary.requested=2, got {summary.get('requested')}"
        assert (
            summary.get("resolved") == 2
        ), f"Expected 2 resolved URLs, got {summary.get('resolved')}"

        resolved = data.get("resolved_drs_object_access_urls", [])
        assert (
            len(resolved) == 2
        ), f"Expected 2 resolved access URL entries, got {len(resolved)}"

        for entry in resolved:
            assert "url" in entry, (
                f"Bulk access URL entry for '{entry.get('drs_object_id')}' "
                f"missing 'url'"
            )
            assert entry[
                "url"
            ], f"Bulk access URL for '{entry.get('drs_object_id')}' is empty"

    def test_bulk_signed_urls_partial_auth(self):
        """
        Scenario: Verify partial auth — authorized and unauthorized GUIDs
        Steps:
            1. Get access ID from an authorized record.
            2. POST /objects/access with authorized + unauthorized object/access pairs.
            3. Verify authorized GUID is resolved, unauthorized is in unresolved.
        """
        # Get access ID from an authorized record
        s3_obj = self.drs.get_drs_object(file=drs_15_indexd_files["s3_available"])
        assert s3_obj.status_code == 200
        s3_methods = s3_obj.json().get("access_methods", [])
        assert len(s3_methods) > 0, "s3_available has no access methods"

        # Use a non-existent object ID for the unauthorized case
        fake_id = str(uuid4())
        bulk_access_ids = [
            {
                "bulk_object_id": drs_15_indexd_files["s3_available"]["did"],
                "bulk_access_ids": [s3_methods[0]["access_id"]],
            },
            {
                "bulk_object_id": fake_id,
                "bulk_access_ids": ["s3"],
            },
        ]

        resp = self.drs.get_bulk_signed_urls(bulk_access_ids=bulk_access_ids)
        assert (
            resp.status_code == 200
        ), f"Expected 200 from bulk signed URLs, got {resp.status_code}"
        data = resp.json()

        summary = data.get("summary", {})
        assert (
            summary.get("requested") == 2
        ), f"Expected summary.requested=2, got {summary.get('requested')}"
        assert (
            summary.get("resolved") == 1
        ), f"Expected 1 resolved, got {summary.get('resolved')}"
        assert (
            summary.get("unresolved") == 1
        ), f"Expected 1 unresolved, got {summary.get('unresolved')}"

        # Verify the fake ID is in unresolved
        unresolved_ids = []
        for entry in data.get("unresolved_drs_objects", []):
            unresolved_ids.extend(entry.get("object_ids", []))
        assert (
            fake_id in unresolved_ids
        ), f"Expected '{fake_id}' in unresolved, got {unresolved_ids}"


@pytest.mark.skipif(
    "fence" not in pytest.deployed_services or "indexd" not in pytest.deployed_services,
    reason="DRS service info tests require both fence and indexd",
)
@pytest.mark.fence
@pytest.mark.drs
class TestDrsServiceInfo:
    """DRS 1.5 service-info endpoint tests."""

    @classmethod
    def setup_class(cls):
        cls.drs = Drs()

        # Version gate and cache service-info response
        try:
            resp = cls.drs.get_service_info()
            if resp.status_code == 200:
                cls.service_info = resp.json()
                version_str = cls.service_info.get("type", {}).get("version", "1.2")
            else:
                version_str = "1.2"
                cls.service_info = {}
        except Exception:
            version_str = "1.2"
            cls.service_info = {}
        if Version(version_str) < Version("1.5"):
            pytest.skip("DRS 1.5 not deployed on this environment")

    def test_service_info_returns_drs_version(self):
        """
        Scenario: Verify service-info reports DRS 1.5 version
        Steps:
            1. Check cached /service-info response.
            2. Verify type.artifact is 'drs' and type.version starts with '1.5'.
        """
        svc_type = self.service_info.get("type", {})
        assert (
            svc_type.get("artifact") == "drs"
        ), f"Expected type.artifact='drs', got '{svc_type.get('artifact')}'"
        version = svc_type.get("version", "")
        assert version.startswith(
            "1.5"
        ), f"Expected type.version to start with '1.5', got '{version}'"

    def test_service_info_drs_stats(self):
        """
        Scenario: Verify DRS-specific stats and backward-compat fields
        Steps:
            1. Check cached /service-info response for drs sub-object.
            2. Verify maxBulkRequestLength, objectCount, and totalObjectSize.
            3. Verify root-level maxBulkRequestLength matches drs.maxBulkRequestLength.
        """
        drs_info = self.service_info.get("drs", {})
        assert (
            "maxBulkRequestLength" in drs_info
        ), "service-info missing drs.maxBulkRequestLength"
        assert isinstance(
            drs_info["maxBulkRequestLength"], int
        ), "drs.maxBulkRequestLength must be an integer"
        assert (
            drs_info["maxBulkRequestLength"] > 0
        ), "drs.maxBulkRequestLength must be positive"
        assert "objectCount" in drs_info, "service-info missing drs.objectCount"
        assert isinstance(
            drs_info["objectCount"], int
        ), "drs.objectCount must be an integer"
        assert "totalObjectSize" in drs_info, "service-info missing drs.totalObjectSize"
        assert isinstance(
            drs_info["totalObjectSize"], int
        ), "drs.totalObjectSize must be an integer"
        # Backward-compat: root-level maxBulkRequestLength
        root_max = self.service_info.get("maxBulkRequestLength")
        assert (
            root_max is not None
        ), "service-info missing root-level maxBulkRequestLength"
        assert root_max == drs_info["maxBulkRequestLength"], (
            f"Root maxBulkRequestLength ({root_max}) does not match "
            f"drs.maxBulkRequestLength ({drs_info['maxBulkRequestLength']})"
        )
