"""
TODO Link to task token docs here

requires:
- MAX_TASK_TOKEN_TTL: {"WORKFLOW": 4000}
- ALLOWED_TASK_TOKEN_TYPES: ["WORKFLOW", "FOO"]
- main_account access to create task tokens up to 4000 (or less?)

JA4 enforcement
- use SDK proxy
  - with `gen3 run`
  - with `curl`
- change the JA4 (how?)
- check that the TES server rejects the token
"""

import time

import jwt
import pytest
import requests
from services.fence import Fence
from services.gen3workflow import Gen3Workflow, mock_auth_endpoint


def get_task_token(
    type="WORKFLOW", user="main_account", expires_in=3600, expected_status_code=200
):
    url = f"{pytest.root_url}/user/credentials/api/access_token?task_token={type}&expires_in={expires_in}"
    res = requests.post(url, json={"api_key": pytest.api_keys[user]["api_key"]})
    assert res.status_code == expected_status_code, res.text
    if res.status_code == 200:
        return res.json()["access_token"]


import gen3
from gen3.dpop import dpop_proxy_context


class TestTaskToken(object):
    @classmethod
    def setup_class(cls):
        cls.fence = Fence()
        cls.gen3_workflow = Gen3Workflow()

    def test_obtain_task_token(self):
        """
        TODO
        """
        # MAX_ACCESS_TOKEN_TTL is 3600 and MAX_TASK_TOKEN_TTL.WORKFLOW is 4000. Check that we can
        # request a WORKFLOW task token > 3600 and <= 4000
        default_max_exp = 3600
        requested_exp = 3777
        now = int(time.time())
        workflow_task_token = get_task_token(expires_in=requested_exp)
        exp = jwt.decode(
            workflow_task_token,
            algorithms=["RS256"],
            options={"verify_signature": False},
        )["exp"]
        assert exp - now >= requested_exp - 1 and exp - now <= requested_exp + 1

        # the longer lifetime should not work for task token type != WORKFLOW since it's not
        # configured. We should get exp == MAX_ACCESS_TOKEN_TTL
        other_task_token = get_task_token("FOO", expires_in=requested_exp)
        exp = jwt.decode(
            other_task_token, algorithms=["RS256"], options={"verify_signature": False}
        )["exp"]
        assert exp - now >= default_max_exp - 1 and exp - now <= default_max_exp + 1

        # requesting a task token with a non-allowed type should not work
        get_task_token("BAR", expected_status_code=400)

        # a user without access to task tokens should not be able to obtain one
        # TODO enable - my arborist allows everything
        # get_task_token(user="dummy_one", expected_status_code=401)

    def test_task_token_audience(self):
        """
        TODO
        """
        user = "main_account"
        regular_token = self.gen3_workflow.get_access_token(user)
        workflow_task_token = get_task_token()
        other_task_token = get_task_token("FOO")

        # fail to use a WORKFLOW task token on a non-WORKFLOW endpoint in Fence
        url = f"{pytest.root_url}/user/user"
        res = requests.get(
            url, headers={"Authorization": f"bearer {workflow_task_token}"}
        )
        assert res.status_code == 401, res.text
        assert "token audience validation failed" in res.text

        # fail to use a WORKFLOW task token on a non-WORKFLOW endpoint outside of Fence
        # TODO uncomment once go-authutils is updated in arborist
        # TODO maybe nvm? https://cdis.slack.com/archives/C02SH3UB2T0/p1785954635381709?thread_ts=1785953406.385109&cid=C02SH3UB2T0
        # url = f"{pytest.root_url}/authz/mapping"
        # res = requests.get(url, headers={"Authorization": f"bearer {workflow_task_token}"})
        # assert res.status_code == 401, res.text
        # assert "token audience validation failed" in res.text

        # fail to use a non-task token on a WORKFLOW endpoint
        # TODO uncomment once gen3-workflow is updated to reject non-task tokens
        # url = f"{pytest.root_url}/ga4gh/tes/v1/tasks"
        # res = requests.get(url, headers={"Authorization": f"bearer {regular_token}"})
        # assert res.status_code == 401, res.text
        # assert "token audience validation failed" in res.text

        # fail to use a non-WORKFLOW task token on a WORKFLOW endpoint
        # TODO uncomment once gen3-workflow is updated to reject non-WORKFLOW task tokens
        # url = f"{pytest.root_url}/ga4gh/tes/v1/tasks"
        # res = requests.get(url, headers={"Authorization": f"bearer {other_task_token}"})
        # assert res.status_code == 401, res.text
        # assert "token audience validation failed" in res.text

        # succeed using a WORKFLOW task token on a WORKFLOW endpoint
        url = f"{pytest.root_url}/ga4gh/tes/v1/tasks"
        res = requests.get(
            url, headers={"Authorization": f"bearer {workflow_task_token}"}
        )
        assert res.status_code == 200, res.text

    def test_denylist_task_token(self):
        """
        TODO
        """
        task_token = get_task_token()

        # check that the token can be used
        url = f"{pytest.root_url}/ga4gh/tes/v1/tasks"
        res = requests.get(url, headers={"Authorization": f"bearer {task_token}"})
        assert res.status_code == 200, res.text

        # denylist the token
        self.fence.revoke_token(task_token)

        # the server should now reject the token
        url = f"{pytest.root_url}/ga4gh/tes/v1/tasks"
        res = requests.get(url, headers={"Authorization": f"bearer {task_token}"})
        assert res.status_code == 403, res.text

    def test_dpop_proxy(self, mock_auth_endpoint):
        """
        TODO
        """
        # from gen3.auth import Gen3Auth
        # auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url)
        auth = self.gen3_workflow._get_auth_module()
        # print('auth.endpoint', auth.endpoint)
        print(
            "endpoint_from_token",
            gen3.auth.endpoint_from_token(pytest.api_keys["main_account"]["api_key"]),
        )  # should be localhost.....

        with dpop_proxy_context(auth=auth, task_token_type="WORKFLOW") as (
            task_token,
            proxy_port,
        ):
            # Anything sent to 127.0.0.1:{proxy_port} is signed and forwarded.
            print("task_token", task_token)
