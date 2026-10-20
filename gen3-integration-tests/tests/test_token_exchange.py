"""
TOKEN EXCHANGE
Exchange a GA4GH passport from the mock passport broker
(gen3_ci/helm_charts/mock-passport-broker) for a fence access token (RFC 8693),
and check the access token grants exactly the dbGaP permissions in the
passport's RAS visa, limited to what the exchanging client may access.
The tests deploy the broker only when they run, and uninstall it when they finish.
"""

import base64
import json
import re

import pytest
from services.drs import Drs
from services.fence import Fence
from services.indexd import Indexd
from utils import gen3_admin_tasks as gat
from utils import logger

TOKEN_EXCHANGE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:token-exchange"
TOKEN_TYPE_ACCESS_TOKEN = "urn:ietf:params:oauth:token-type:access_token"
TOKEN_TYPE_GA4GH_PASSPORT = "urn:ga4gh:params:oauth:token-type:passport"
TOKEN_TYPE_JWT = "urn:ietf:params:oauth:token-type:jwt"
RAS_VISA_TYPE = "https://ras.nih.gov/visas/v1.1"

SCOPE = "openid user data"

# Arborist only authorizes a token issued to a client for what both the user and the
# client may access. Each client's policy is defined in the CI user.yaml
# (https://github.com/uc-cdis/commons-users/blob/master/users/ci/user.yaml), with the
# resource paths it covers here (None for every program)
DEFAULT_CLIENT_POLICY = "all_programs_reader"
RESTRICTED_CLIENT_POLICY = "token_exchange_restricted_reader"
TOKEN_EXCHANGE_CLIENTS = {
    # reads any program's data, so the passport alone decides which files the token reaches
    DEFAULT_CLIENT_POLICY: {
        "name": "token-exchange-test-client",
        "resource_paths": None,
    },
    # reads one of the datasets the passport grants, so the token reaches only that one
    RESTRICTED_CLIENT_POLICY: {
        "name": "token-exchange-restricted-client",
        "resource_paths": ["/programs/phs002410.c2"],
    },
}
FILE_CONTENT = "Hi Zac!\ncdis-data-client uploaded this!\n"
FILE_MD5 = "73d643ec3f4beb9020eef0beed440ad0"  # pragma: allowlist secret

# Consent groups of the passport's studies that its ras_dbgap_permissions do not grant
PERMISSIONS_NOT_IN_PASSPORT = [
    {"phs_id": "phs000710", "consent_group": "c1"},
    {"phs_id": "phs002410", "consent_group": "c1"},
]


def get_resource_path(permission):
    """The arborist resource fence syncs a ras_dbgap_permission to"""
    return f"/programs/{permission['phs_id']}.{permission['consent_group']}"


def make_indexd_record(authz):
    return {
        "acl": [],
        "authz": [authz],
        "file_name": "token_exchange_test_file",
        "hashes": {"md5": FILE_MD5},
        "size": 9,
        "urls": ["s3://cdis-presigned-url-test/testdata"],
    }


def get_unverified_claims(token):
    """Decode the claims of a JWT without verifying its signature"""
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def replace_claims(token, claims):
    """Swap the claims of a JWT, keeping its header and (now invalid) signature"""
    header, _, signature = token.split(".")
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode()
    return f"{header}.{payload.rstrip('=')}.{signature}"


@pytest.mark.skipif(
    "fence" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.skipif(
    "indexd" not in pytest.deployed_services,
    reason="indexd service is not running on this environment",
)
@pytest.mark.fence
@pytest.mark.indexd
@pytest.mark.drs
@pytest.mark.token_exchange
class TestTokenExchange:
    @classmethod
    def setup_class(cls):
        cls.fence = Fence()
        cls.drs = Drs()
        cls.indexd = Indexd()
        cls.variables = {}
        cls.variables["created_indexd_dids"] = []
        cls.clients = {}

        # skip all these tests if fence does not support token exchange
        grant_types = cls.fence.get_openid_configuration().get(
            "grant_types_supported", []
        )
        if TOKEN_EXCHANGE_GRANT_TYPE not in grant_types:
            pytest.skip("Token exchange is not enabled in fence on this environment")

        # Deploy the broker only now that we know these tests will run. pytest does
        # not call teardown_class when setup_class fails, so clean up here instead
        try:
            gat.deploy_mock_passport_broker(test_env_namespace=pytest.namespace)
            cls.create_test_data()
        except BaseException:
            cls.teardown_class()
            raise

    @classmethod
    def create_test_data(cls):
        """Get a passport from the broker, and create the clients and indexd records"""
        # The access token should grant exactly the ras_dbgap_permissions in the
        # passport's RAS visa (see generate_passport.py in the mock-passport-broker chart)
        cls.passport = gat.get_passport_from_mock_passport_broker(
            test_env_namespace=pytest.namespace
        )
        visas = [
            get_unverified_claims(visa)
            for visa in get_unverified_claims(cls.passport)["ga4gh_passport_v1"]
        ]
        cls.ras_dbgap_permissions = [
            permission
            for visa in visas
            if visa["ga4gh_visa_v1"]["type"] == RAS_VISA_TYPE
            for permission in visa.get("ras_dbgap_permissions", [])
        ]
        logger.info(f"ras_dbgap_permissions in passport: {cls.ras_dbgap_permissions}")
        assert cls.ras_dbgap_permissions, "Passport has no ras_dbgap_permissions"
        cls.resource_paths_in_passport = sorted(
            {get_resource_path(permission) for permission in cls.ras_dbgap_permissions}
        )
        cls.resource_paths_not_in_passport = [
            get_resource_path(permission) for permission in PERMISSIONS_NOT_IN_PASSPORT
        ]
        assert not set(cls.resource_paths_not_in_passport) & set(
            cls.resource_paths_in_passport
        ), "PERMISSIONS_NOT_IN_PASSPORT overlaps the passport's ras_dbgap_permissions"

        restricted_resource_paths = TOKEN_EXCHANGE_CLIENTS[RESTRICTED_CLIENT_POLICY][
            "resource_paths"
        ]
        assert set(restricted_resource_paths) < set(
            cls.resource_paths_in_passport
        ), f"{RESTRICTED_CLIENT_POLICY} must cover some, but not all, of the passport's resource paths"

        # Create confidential clients allowed to use the token exchange grant
        for policy, client in TOKEN_EXCHANGE_CLIENTS.items():
            _, client_info = gat.setup_fence_test_client(
                pytest.namespace,
                (client["name"], None, "token_exchange", policy, None, SCOPE),
            )
            client_id, client_secret = re.sub(r"[\'()]", "", client_info).split(", ")
            cls.clients[policy] = {
                "client_id": client_id,
                "client_secret": client_secret,
            }

        # Adding indexd files, with and without authz granted by the passport
        cls.indexd_files = {}
        for authz in (
            cls.resource_paths_in_passport + cls.resource_paths_not_in_passport
        ):
            cls.indexd_files[authz] = make_indexd_record(authz)
            indexd_record = cls.indexd.create_records(
                records={authz: cls.indexd_files[authz]}
            )
            cls.variables["created_indexd_dids"].append(indexd_record[0]["did"])

    @classmethod
    def teardown_class(cls):
        try:
            cls.indexd.delete_records(cls.variables["created_indexd_dids"])
            for policy, client in cls.clients.items():
                gat.delete_fence_test_client(
                    TOKEN_EXCHANGE_CLIENTS[policy]["name"],
                    client_id=client["client_id"],
                    test_env_namespace=pytest.namespace,
                )
        finally:
            gat.delete_mock_passport_broker(test_env_namespace=pytest.namespace)

    def exchange_passport(
        self,
        passport=None,
        subject_token_type=TOKEN_TYPE_GA4GH_PASSPORT,
        client_policy=DEFAULT_CLIENT_POLICY,
    ):
        client = self.clients[client_policy]
        return self.fence.exchange_token(
            client_id=client["client_id"],
            client_secret=client["client_secret"],
            subject_token=passport or self.passport,
            subject_token_type=subject_token_type,
            scope=SCOPE,
        )

    def get_access_token(self, client_policy=DEFAULT_CLIENT_POLICY):
        response = self.exchange_passport(client_policy=client_policy)
        assert (
            response.status_code == 200
        ), f"Expected status 200 but got {response.status_code}: {response.text}"
        return response.json()["access_token"]

    def get_resource_paths_for_client(self, client_policy):
        """The passport's resource paths that the client's policy also covers"""
        client_resource_paths = TOKEN_EXCHANGE_CLIENTS[client_policy]["resource_paths"]
        if client_resource_paths is None:
            return self.resource_paths_in_passport
        return [
            resource_path
            for resource_path in self.resource_paths_in_passport
            if resource_path in client_resource_paths
        ]

    @pytest.mark.parametrize(
        "subject_token_type",
        [TOKEN_TYPE_GA4GH_PASSPORT, TOKEN_TYPE_JWT],
        ids=["ga4gh_passport", "jwt"],
    )
    def test_exchange_passport_for_access_token(self, subject_token_type):
        """
        Scenario: Exchange a passport for an access token
        Steps:
            1. Exchange the passport for an access token.
            2. Validate the response is an access_token with a Bearer token_type, a valid expires_in, the appropriate
               scopes are set, and no refresh_token is issued.
        """
        response = self.exchange_passport(subject_token_type=subject_token_type)
        assert (
            response.status_code == 200
        ), f"Expected status 200 but got {response.status_code}: {response.text}"
        token = response.json()
        assert token.get("access_token"), f"access_token is missing in {token}"
        assert (
            token.get("issued_token_type") == TOKEN_TYPE_ACCESS_TOKEN
        ), f"Expected issued_token_type {TOKEN_TYPE_ACCESS_TOKEN} in {token}"
        assert token.get("token_type") == "Bearer", f"Expected Bearer in {token}"
        # the visas in the passport expire within the hour, and so must the token
        assert (
            0 < token.get("expires_in", 0) <= 3600
        ), f"Expected expires_in between 0 and 3600 in {token}"
        assert set(token.get("scope", "").split()) == set(
            SCOPE.split()
        ), f"Expected scope '{SCOPE}' in {token}"
        # a refresh token would outlive the visas that justified the exchange
        assert "refresh_token" not in token, f"Unexpected refresh_token in {token}"

    def test_user_info_contains_passport_permissions(self):
        """
        Scenario: The exchanged access token has the passport's dbGaP permissions
        Steps:
            1. Exchange the passport for an access token.
            2. Get the user info from /user/user with the access token.
            3. Validate the user has read and read-storage on the resource path of
               every ras_dbgap_permission in the passport.
            4. Validate the user has no access to other consent groups.
        """
        user_info = self.fence.get_user_info(access_token=self.get_access_token())
        resources = user_info["resources"]
        for resource_path in self.resource_paths_in_passport:
            assert (
                resource_path in resources
            ), f"Expected {resource_path} in user resources {resources}"
            methods = {
                permission["method"] for permission in user_info["authz"][resource_path]
            }
            assert {
                "read",
                "read-storage",
            } <= methods, (
                f"Expected read and read-storage on {resource_path} but got {methods}"
            )
        for resource_path in self.resource_paths_not_in_passport:
            assert (
                resource_path not in resources
            ), f"Did not expect {resource_path} in user resources {resources}"

    @pytest.mark.parametrize("client_policy", list(TOKEN_EXCHANGE_CLIENTS))
    def test_drs_access_with_passport_permissions(self, client_policy):
        """
        Scenario: Get DRS presigned urls for files the passport and the client both grant access to
        Steps:
            1. Exchange the passport for an access token with a client allowed to read
               every program, or only one of the passport's datasets.
            2. For every ras_dbgap_permission in the passport that the client's policy
               also covers, get the DRS presigned url of a file with that authz using
               the access token.
            3. Validate the presigned urls are created and the file contents match.
        """
        access_token = self.get_access_token(client_policy=client_policy)
        for resource_path in self.get_resource_paths_for_client(client_policy):
            url, status_code = self.drs.get_drs_signed_url_using_gen3sdk(
                file=self.indexd_files[resource_path], access_token=access_token
            )
            assert (
                status_code == 200
            ), f"Expected status 200 for a file with authz {resource_path} but got {status_code}"
            contents = self.fence.get_file(url)
            assert (
                contents == FILE_CONTENT
            ), f"Data don't match.\n{contents}\n{FILE_CONTENT}"

    @pytest.mark.parametrize("client_policy", list(TOKEN_EXCHANGE_CLIENTS))
    def test_drs_access_without_passport_permissions(self, client_policy):
        """
        Scenario: DRS presigned urls fail for files the passport does not grant access to
        Steps:
            1. Exchange the passport for an access token with a client allowed to read
               every program, or only one of the passport's datasets.
            2. Get the DRS presigned url of files in other consent groups of the
               passport's studies using the access token.
            3. Validate the presigned urls are not created.
        """
        access_token = self.get_access_token(client_policy=client_policy)
        for resource_path in self.resource_paths_not_in_passport:
            _, status_code = self.drs.get_drs_signed_url_using_gen3sdk(
                file=self.indexd_files[resource_path], access_token=access_token
            )
            assert (
                status_code == 401
            ), f"Expected status 401 for a file with authz {resource_path} but got {status_code}"

    def test_drs_access_outside_client_policy(self):
        """
        Scenario: DRS presigned urls fail for files the passport grants access to but the client does not
        Steps:
            1. Exchange the passport for an access token with a client allowed to read
               only one of the passport's datasets.
            2. Validate /user/user still lists the passport's other datasets: it reports
               the user's access, which the client does not restrict.
            3. Get the DRS presigned url of files in the passport's other datasets using
               the access token.
            4. Validate the presigned urls are not created.
        """
        access_token = self.get_access_token(client_policy=RESTRICTED_CLIENT_POLICY)
        resource_paths_outside_client_policy = [
            resource_path
            for resource_path in self.resource_paths_in_passport
            if resource_path
            not in self.get_resource_paths_for_client(RESTRICTED_CLIENT_POLICY)
        ]
        resources = self.fence.get_user_info(access_token=access_token)["resources"]
        for resource_path in resource_paths_outside_client_policy:
            assert (
                resource_path in resources
            ), f"Expected {resource_path} in user resources {resources}"
            _, status_code = self.drs.get_drs_signed_url_using_gen3sdk(
                file=self.indexd_files[resource_path], access_token=access_token
            )
            assert (
                status_code == 401
            ), f"Expected status 401 for a file with authz {resource_path} but got {status_code}"

    def test_tampered_passport_is_rejected(self):
        """
        Scenario: A passport with an added dbGaP permission is rejected
        Steps:
            1. Add a permission the passport does not grant to its RAS visa, without
               re-signing the visa or the passport.
            2. Exchange the tampered passport.
            3. Validate fence rejects it with invalid_grant.
        """
        passport_claims = get_unverified_claims(self.passport)
        tampered_visas = []
        for visa in passport_claims["ga4gh_passport_v1"]:
            visa_claims = get_unverified_claims(visa)
            if visa_claims["ga4gh_visa_v1"]["type"] == RAS_VISA_TYPE:
                permissions = visa_claims["ras_dbgap_permissions"]
                permissions.append({**permissions[0], **PERMISSIONS_NOT_IN_PASSPORT[0]})
                visa = replace_claims(visa, visa_claims)
            tampered_visas.append(visa)
        passport_claims["ga4gh_passport_v1"] = tampered_visas
        tampered_passport = replace_claims(self.passport, passport_claims)

        response = self.exchange_passport(passport=tampered_passport)
        assert (
            response.status_code == 400
        ), f"Expected status 400 but got {response.status_code}: {response.text}"
        assert (
            response.json().get("error") == "invalid_grant"
        ), f"Expected invalid_grant but got {response.text}"
