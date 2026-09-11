"""
See Fence task token docs:
https://github.com/uc-cdis/fence/blob/master/docs/additional_documentation/task_tokens.md

The task token integration with Gen3Workflow/TES is included in `tests/test_gen3_workflow.py`.

TODO for CI requires:
- MAX_TASK_TOKEN_TTL: {"WORKFLOW": 4000}
- ALLOWED_TASK_TOKEN_TYPES: ["WORKFLOW", "FOO"]
- main_account access to create task tokens up to 4000 (or less?)
- enabling and configuring dpop in fence and gen3-workflow
"""

import time

import jwt
import pytest
import requests
import utils.gen3_admin_tasks as gat
from services.fence import Fence
from services.gen3workflow import Gen3Workflow, WorkflowStorageConfig


@pytest.mark.skipif(
    "fence" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
)
@pytest.mark.skipif(
    gat.service_version_lower_than("fence", "2026.10", "13.4.0"),
    reason="Current fence version doesn't have the changes for this test",
)
@pytest.mark.fence
class TestTaskToken(object):
    @classmethod
    def setup_class(cls):
        cls.fence = Fence()
        cls.gen3_workflow = Gen3Workflow()
        cls.s3_storage_config = WorkflowStorageConfig.from_dict(
            cls.gen3_workflow.setup_storage()
        )

    def test_obtain_task_token(self):
        """
        Test that task tokens are only given to users with access, and only for valid DPoP requests.
        """
        # should NOT be able to obtain a task token without going through the DPoP proxy
        url = f"{pytest.root_url}/user/credentials/api/access_token?task_token=WORKFLOW"
        res = requests.post(
            url, json={"api_key": pytest.api_keys["main_account"]["api_key"]}
        )
        assert res.status_code == 400, res.text
        assert "Invalid DPoP request" in res.text

        # should be able to obtain a task token by going through the DPoP proxy.
        # MAX_ACCESS_TOKEN_TTL is 3600 and MAX_TASK_TOKEN_TTL.WORKFLOW is 4000. Check that we can
        # request a WORKFLOW task token with a lifetime > 3600 and <= 4000
        default_max_exp = 3600
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
        assert exp - now >= requested_exp - 1 and exp - now <= requested_exp

        # a lifetime > MAX_ACCESS_TOKEN_TTL should not work for task token type != WORKFLOW since
        # it's not configured in MAX_TASK_TOKEN_TTL. We should get exp == MAX_ACCESS_TOKEN_TTL
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
        assert exp - now >= default_max_exp - 1 and exp - now <= default_max_exp

        # requesting a task token with a non-allowed type (not configured in
        # ALLOWED_TASK_TOKEN_TYPES) should not work
        self.fence.get_dpop_bound_task_token("BAR", expected_status_code=400)

        # a user without access to task tokens should not be able to obtain one
        # TODO enable - my arborist allows everything
        # self.fence.get_dpop_bound_task_token("WORKFLOW", user="dummy_one", expected_status_code=401)

    def test_task_token_audience(self):
        """
        Test that task tokens can only be used on the endpoints they are meant for, and that those
        endpoints reject non-task tokens.
        """
        # fail to use a regular (non-DPoP, non-task) token on a WORKFLOW endpoint
        regular_token = self.gen3_workflow.get_access_token("main_account")
        url = f"{pytest.root_url}/ga4gh/tes/v1/tasks"
        res = requests.get(url, headers={"Authorization": f"bearer {regular_token}"})
        assert res.status_code == 401, "Should not be allowed to list TES tasks"
        assert res.json().get("error") == "dpop_required"

        with self.fence.get_dpop_bound_task_token("WORKFLOW") as (
            workflow_task_token,
            proxy_url,
        ):
            # fail to use a WORKFLOW task token on a non-WORKFLOW endpoint in Fence
            url = f"{pytest.root_url}/user/user"
            res = requests.get(
                url, headers={"Authorization": f"bearer {workflow_task_token}"}
            )
            assert res.status_code == 401, res.text
            assert "token audience validation failed" in res.text

            # fail to use a WORKFLOW task token on a non-WORKFLOW endpoint outside of Fence
            # TODO service other than arborist, where authutils is updated

            # succeed using a WORKFLOW task token on a WORKFLOW endpoint
            res = requests.get(
                f"{proxy_url}/ga4gh/tes/v1/tasks",
                headers={"Authorization": f"bearer {workflow_task_token}"},
            )
            assert res.status_code == 200, res.text

        with self.fence.get_dpop_bound_task_token("FOO") as (
            foo_task_token,
            proxy_url,
        ):
            # fail to use a non-WORKFLOW task token on a WORKFLOW endpoint
            url = f"{proxy_url}/ga4gh/tes/v1/tasks"
            res = requests.get(
                url, headers={"Authorization": f"bearer {foo_task_token}"}
            )
            assert res.status_code == 401, "Should not be allowed to list TES tasks"
            assert "token audience validation failed" in res.text

            # succeed using a task token on an Arborist endpoint, regardless of task token type,
            # since Arborist should accept all tokens for authorization verification purposes
            url = f"{pytest.root_url}/authz/mapping"
            res = requests.get(
                url, headers={"Authorization": f"bearer {foo_task_token}"}
            )
            assert res.status_code == 200, res.text

    def test_denylist_task_token(self):
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
