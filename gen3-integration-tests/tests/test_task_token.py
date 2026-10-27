"""
See Fence task token docs:
https://github.com/uc-cdis/fence/blob/master/docs/additional_documentation/task_tokens.md

The task token integration with Gen3Workflow/TES is included in `tests/test_gen3_workflow.py`.
"""

import time

import jwt
import pytest
import requests
import utils.gen3_admin_tasks as gat
from services.fence import Fence
from services.gen3workflow import Gen3Workflow

# allow extra time for the proxy startup, the nonce challenge/retry round trip, the
# arborist call, etc
PROXY_GRACE_PERIOD_SEC = 30


@pytest.mark.skipif(
    "fence" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.skipif(
    gat.service_version_lower_than("fence", "2026.11", "15.0.0"),
    reason="Current fence version doesn't have the changes for this test",
)
@pytest.mark.fence
class TestTaskToken(object):
    @classmethod
    def setup_class(cls):
        cls.fence = Fence()

    def test_obtain_task_token_failure_without_proxy(self):
        """
        Test that task tokens are only given to users with access, and only for valid DPoP requests.
        """
        url = f"{pytest.root_url}/user/credentials/api/access_token?task_token=WORKFLOW"
        res = requests.post(
            url, json={"api_key": pytest.api_keys["main_account"]["api_key"]}
        )
        assert res.status_code == 400, res.text
        assert "Invalid DPoP request" in res.text

    def test_obtain_task_token_success(self):
        """
        Should be able to obtain a task token by going through the DPoP proxy.

        MAX_ACCESS_TOKEN_TTL is 3600 and MAX_TASK_TOKEN_TTL.WORKFLOW is 4000. We can
        request a WORKFLOW task token with a lifetime > 3600 and <= 4000.
        """
        requested_exp = 3777
        with self.fence.get_dpop_bound_task_token(
            "WORKFLOW", expires_in=requested_exp
        ) as (
            workflow_task_token,
            _,
        ):
            exp = jwt.decode(
                workflow_task_token,
                algorithms=["RS256"],
                options={"verify_signature": False},
            )["exp"]
        now = int(time.time())
        assert requested_exp - PROXY_GRACE_PERIOD_SEC <= exp - now <= requested_exp

    def test_obtain_task_token_max_ttl(self):
        """
        Should be able to obtain a task token by going through the DPoP proxy.

        A lifetime > MAX_ACCESS_TOKEN_TTL should not work for task token type != WORKFLOW since
        it's not configured in MAX_TASK_TOKEN_TTL. We should get exp == MAX_ACCESS_TOKEN_TTL.

        TODO: add test case for a user that has access to a specific task token lifetime,
        e.g. "/services/fence/task-token/WORKFLOW/4000" once this is done:
        https://ctds-planx.atlassian.net/browse/MIDRC-1319
        """
        default_max_exp = 3600
        requested_exp = 3777
        with self.fence.get_dpop_bound_task_token("FOO", expires_in=requested_exp) as (
            other_task_token,
            _,
        ):
            exp = jwt.decode(
                other_task_token,
                algorithms=["RS256"],
                options={"verify_signature": False},
            )["exp"]
        now = int(time.time())
        assert default_max_exp - PROXY_GRACE_PERIOD_SEC <= exp - now <= default_max_exp

    def test_obtain_task_token_unsupported_type(self):
        """
        Requesting a task token with a non-allowed type (not configured in Fence's
        ALLOWED_TASK_TOKEN_TYPES) should not work.
        """
        with self.fence.get_dpop_bound_task_token("BAR", expected_status_code=400) as (
            token,
            url,
        ):
            assert token == None
            assert url == None

    def test_obtain_task_token_unauthorized(self):
        """
        A user without access to task tokens should not be able to obtain one
        """
        with self.fence.get_dpop_bound_task_token(
            "WORKFLOW", user="user2_account", expected_status_code=403
        ) as (token, url):
            assert token == None
            assert url == None

    def test_task_token_against_arborist(self):
        """
        Succeed using a task token on an Arborist endpoint, regardless of task token type,
        since Arborist should accept all tokens for authorization verification purposes
        """
        with self.fence.get_dpop_bound_task_token("FOO") as (foo_task_token, _):
            url = f"{pytest.root_url}/authz/mapping"
            res = requests.get(
                url, headers={"Authorization": f"bearer {foo_task_token}"}
            )
            assert res.status_code == 200, res.text


@pytest.mark.skipif(
    "gen3-workflow" not in pytest.deployed_services,
    reason="gen3-workflow service is not running on this environment",
)
@pytest.mark.skipif(
    "funnel" not in pytest.deployed_services,
    reason="funnel service is not running on this environment",
)
@pytest.mark.skipif(
    "localhost" in pytest.hostname,
    reason="DPoP is not supported by the Kind CI",
)
@pytest.mark.gen3_workflow
class TestTaskTokenWithGen3Workflow:
    """
    Using a separate class so we can apply the pytest marks above to all the tests that require
    gen3-workflow without repeating them for each test.
    """

    @classmethod
    def setup_class(cls):
        cls.fence = Fence()
        cls.gen3_workflow = Gen3Workflow()
        cls.gen3_workflow.setup_storage()

    def test_dpop_task_token_endpoints_with_regular_token(self):
        """
        Use a regular token to hit an endpoint that requires DPoP-bound task tokens.
        """
        with self.gen3_workflow.get_token_and_gen3_url("main_account") as (
            regular_token,
            _,
        ):
            # fail to use a regular (non-DPoP, non-task) token on a WORKFLOW endpoint that requires
            # DPoP
            url = f"{pytest.root_url}/ga4gh/tes/v1/tasks"
            res = requests.post(
                url, headers={"Authorization": f"bearer {regular_token}"}
            )
            assert res.status_code == 401, "Should not be allowed to create a TES task"
            assert res.json().get("error") == "dpop_required"

            # fail to use a regular (non-DPoP, non-task) token on a WORKFLOW endpoint that requires
            # DPoP, even when using the `dpop` keyword instead of the `bearer` keyword in the auth
            # header
            url = f"{pytest.root_url}/ga4gh/tes/v1/tasks"
            res = requests.post(url, headers={"Authorization": f"dpop {regular_token}"})
            assert res.status_code == 401, "Should not be allowed to create a TES task"
            assert res.json().get("error") == "dpop_required"

    def test_non_dpop_task_token_endpoints_with_regular_token(self):
        """
        Use a regular token to hit an endpoint that supports, but does not require, DPoP-bound task
        tokens.
        """
        with self.gen3_workflow.get_token_and_gen3_url("main_account") as (
            regular_token,
            _,
        ):
            # using the `bearer` scheme: should succeed
            url = f"{pytest.root_url}/ga4gh/tes/v1/tasks"
            res = requests.get(
                url, headers={"Authorization": f"bearer {regular_token}"}
            )
            assert res.status_code == 200, "Should be allowed to list TES tasks"

            # using the `dpop` scheme without using a DPoP-bound token: should fail
            res = requests.get(url, headers={"Authorization": f"dpop {regular_token}"})
            assert res.status_code == 401, "Should not be allowed to list TES tasks"
            assert res.json().get("error") == "dpop_required"

    def test_call_task_token_endpoint_anonymously(self):
        """
        Anonymous calls fail on WORKFLOW endpoints that requires DPoP, and
        succeed on WORKFLOW endpoints that do NOT require DPoP
        """
        # DPoP required: anonymous call rejected
        url = f"{pytest.root_url}/ga4gh/tes/v1/tasks"
        res = requests.post(url)
        assert (
            res.status_code == 401
        ), "Anonynous user should not be allowed to create a TES task"
        assert res.json().get("error") == "dpop_required"

        # DPoP not required: anonymous call accepted
        res = requests.get(f"{url}?all")
        assert (
            res.status_code == 200
        ), "Anonynous user should be allowed to list TES tasks"

    def test_task_token_audience_mismatch(self):
        """
        Fail to use a WORKFLOW task token on non-WORKFLOW endpoints.
        Fail to use a non-WORKFLOW task token on a WORKFLOW endpoint.
        """
        with self.fence.get_dpop_bound_task_token("WORKFLOW") as (
            workflow_task_token,
            _,
        ):
            # should fail to hit a Fence endpoint with a WORKFLOW token
            url = f"{pytest.root_url}/user/user"
            res = requests.get(
                url, headers={"Authorization": f"bearer {workflow_task_token}"}
            )
            assert res.status_code == 401, res.text
            assert "token audience validation failed" in res.text

            # should fail to hit a non-Fence, non-WORKFLOW endpoint (indexd) with a WORKFLOW token
            # TODO uncomment once https://github.com/uc-cdis/indexd/pull/463 is merged
            # data = {
            #     "form": "object",
            #     "size": 0,
            #     "urls": [],
            #     "hashes": {"md5": "f36c8c3a550320a66b780768320d14bb"},
            # }
            # res = requests.post(
            #     f"{pytest.root_url}/index/index",
            #     json=data,
            #     headers={"Authorization": f"bearer {workflow_task_token}"},
            # )
            # assert res.status_code == 401, res.text
            # assert "token audience validation failed" in res.text

        # should fail to hit a WORKFLOW endpoint with a non-WORKFLOW token
        with self.fence.get_dpop_bound_task_token("FOO") as (
            foo_task_token,
            proxy_url,
        ):
            url = f"{proxy_url}/ga4gh/tes/v1/tasks"
            res = requests.get(
                url, headers={"Authorization": f"bearer {foo_task_token}"}
            )
            assert res.status_code == 401, "Should not be allowed to list TES tasks"
            assert (
                "The access token is missing, malformed, expired or not accepted here"
                in res.text
            )

    def test_task_token_success_when_required(self, request):
        """
        Succeed using a WORKFLOW task token on a WORKFLOW endpoint that requires DPoP
        """
        with self.fence.get_dpop_bound_task_token("WORKFLOW") as (
            workflow_task_token,
            proxy_url,
        ):
            res = requests.post(
                f"{proxy_url}/ga4gh/tes/v1/tasks",
                headers={"Authorization": f"bearer {workflow_task_token}"},
                json={
                    "name": request.node.name,
                    "executors": [
                        {
                            "image": "public.ecr.aws/docker/library/alpine:latest",
                            "command": ["echo done"],
                        }
                    ],
                },
            )
            assert res.status_code == 200, res.text
            task_id = res.json()["id"]

            # clean up: cancel the task we just created
            res = requests.post(
                url=f"{proxy_url}/ga4gh/tes/v1/tasks/{task_id}:cancel",
                headers={"Authorization": f"bearer {workflow_task_token}"},
            )
            assert res.status_code == 200, "Failed to cancel task"

    def test_task_token_success_when_not_required(self):
        """
        Succeed using a WORKFLOW task token on a WORKFLOW endpoint, even if it does not
        require DPoP
        """
        with self.fence.get_dpop_bound_task_token("WORKFLOW") as (
            workflow_task_token,
            proxy_url,
        ):
            res = requests.get(
                f"{proxy_url}/ga4gh/tes/v1/tasks",
                headers={"Authorization": f"bearer {workflow_task_token}"},
            )
            assert res.status_code == 200, res.text

    def test_task_token_denylist(self):
        """
        Test that task tokens can be revoked/denylisted, after which they should not be accepted by
        the server anymore.
        """
        with self.fence.get_dpop_bound_task_token("WORKFLOW") as (
            task_token,
            proxy_url,
        ):
            # check that the token can be used
            url = f"{proxy_url}/ga4gh/tes/v1/tasks"
            res = requests.get(url, headers={"Authorization": f"bearer {task_token}"})
            assert res.status_code == 200, res.text

            # denylist the token
            self.fence.revoke_token(task_token)

            # the server should now reject the token
            url = f"{proxy_url}/ga4gh/tes/v1/tasks"
            res = requests.get(url, headers={"Authorization": f"bearer {task_token}"})
            assert res.status_code == 403, "Should not be allowed to list TES tasks"
