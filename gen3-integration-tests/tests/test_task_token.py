"""
TODO Link to task token docs here

- obtain a TES token with a lifetime >1h
- check that the expiration matches the expected lifetime
- fail to obtain a TES token if you don't have access
Audience check
- fail to use it for something else than TES
- succeed using it on a TES endpoint
- fail to use a non-TES task token on a TES endpoint
- fail to use a non-task token on a TES endpoint
JA4 enforcement
- use SDK proxy
- change the JA4 (how?)
- check that the TES server rejects the token
Blacklisting
- revoke the token through the "/credentials/token/blacklisted" endpoint
- check that the TES server rejects the token
Requestor integration
- TBD
"""

import time

import jwt
import pytest
import requests
from services.gen3workflow import Gen3Workflow


def get_task_token(
    type="WORKFLOW", user="main_account", expires_in=3600, expected_status_code=200
):
    url = f"{pytest.root_url}/user/credentials/api/access_token?task_token={type}&expires_in={expires_in}"
    res = requests.post(url, json={"api_key": pytest.api_keys[user]["api_key"]})
    assert res.status_code == expected_status_code, res.text
    if res.status_code == 200:
        return res.json()["access_token"]


class TestTaskToken(object):
    @classmethod
    def setup_class(cls):
        cls.gen3_workflow = Gen3Workflow()

    def test_task_token_endpoints(self):
        """
        TODO

        requires:
        - MAX_TASK_TOKEN_TTL: {"WORKFLOW": 4000}
        - ALLOWED_TASK_TOKEN_TYPES: ["WORKFLOW", "FOO"]
        - main_account access to create task tokens up to 4000 (or less?)
        """
        user = "main_account"
        regular_token = self.gen3_workflow._get_access_token(user)

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

        # a user without access should not be able to obtain a task token
        # TODO enable - my arborist allows everything
        # get_task_token(user="dummy_one", expected_status_code=401)

        # fail to use a WORKFLOW task token on non-WORKFLOW endpoints in Fence
        url = f"{pytest.root_url}/user/user"
        res = requests.get(
            url, headers={"Authorization": f"bearer {workflow_task_token}"}
        )
        assert res.status_code == 401, res.text
        assert "token audience validation failed" in res.text

        # fail to use a WORKFLOW task token on non-WORKFLOW endpoints outside of Fence
        # TODO uncomment once go-authutils is updated in arborist
        # url = f"{pytest.root_url}/authz/mapping"
        # res = requests.get(url, headers={"Authorization": f"bearer {workflow_task_token}"})
        # assert res.status_code == 401, res.text

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
