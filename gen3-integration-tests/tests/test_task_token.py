"""
TODO Link to task token docs here

requires:
- MAX_TASK_TOKEN_TTL: {"WORKFLOW": 4000}
- ALLOWED_TASK_TOKEN_TYPES: ["WORKFLOW", "FOO"]
- main_account access to create task tokens up to 4000 (or less?)
- enabling and configuring dpop in fence and gen3-workflow

JA4 enforcement
- use SDK proxy
  - with `gen3 run`
  - with `curl`
- change the JA4 (how?)
  - then check that the TES server rejects the token

TODO update the other gen3-workflow tests
TODO disable when fence or gen3-workflow version is too low
"""

import tempfile
import time
from contextlib import contextmanager

import jwt
import pytest
import requests

# import gen3
from gen3.auth import Gen3Auth
from gen3.dpop import dpop_proxy_context
from services.fence import Fence
from services.gen3workflow import (
    Gen3Workflow,
    WorkflowStorageConfig,
    nextflow_parse_completed_line,
    nextflow_parse_completed_tasks,
)
from utils import logger

DPOP_PROXY_URL = "http://127.0.0.1"


@contextmanager
def get_dpop_task_token(
    type="WORKFLOW", user="main_account", expires_in=3600, expected_status_code=200
):
    auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
    try:
        with dpop_proxy_context(
            auth=auth, task_token_type=type, task_token_expiration=expires_in
        ) as (task_token, proxy_port):
            yield task_token, proxy_port
    except Exception as e:
        if expected_status_code == 200:
            raise
        assert f"[{expected_status_code}]" in str(e)


@pytest.mark.skipif(
    "fence" not in pytest.deployed_services,
    reason="fence service is not running on this environment",
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
        TODO
        """
        # MAX_ACCESS_TOKEN_TTL is 3600 and MAX_TASK_TOKEN_TTL.WORKFLOW is 4000. Check that we can
        # request a WORKFLOW task token with a lifetime > 3600 and <= 4000
        default_max_exp = 3600
        requested_exp = 3777
        with get_dpop_task_token(expires_in=requested_exp) as (workflow_task_token, _):
            exp = jwt.decode(
                workflow_task_token,
                algorithms=["RS256"],
                options={"verify_signature": False},
            )["exp"]
        now = int(time.time())
        assert exp - now >= requested_exp - 1 and exp - now <= requested_exp

        # the longer lifetime should not work for task token type != WORKFLOW since it's not
        # configured. We should get exp == MAX_ACCESS_TOKEN_TTL
        with get_dpop_task_token("FOO", expires_in=requested_exp) as (
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

        # requesting a task token with a non-allowed type should not work
        get_dpop_task_token("BAR", expected_status_code=400)

        # a user without access to task tokens should not be able to obtain one
        # TODO enable - my arborist allows everything
        # get_dpop_task_token(user="dummy_one", expected_status_code=401)

    def test_task_token_audience(self):
        """
        TODO
        """
        user = "main_account"

        # fail to use a non-DPoP, non-task token on a WORKFLOW endpoint
        regular_token = self.gen3_workflow.get_access_token(user)
        url = f"{pytest.root_url}/ga4gh/tes/v1/tasks"
        res = requests.get(url, headers={"Authorization": f"bearer {regular_token}"})
        assert res.status_code == 401, "Should not be allowed to list TES tasks"
        assert res.json().get("error") == "dpop_required"

        with get_dpop_task_token() as (workflow_task_token, proxy_port):
            # fail to use a WORKFLOW task token on a non-WORKFLOW endpoint in Fence
            url = f"{pytest.root_url}/user/user"
            res = requests.get(
                url, headers={"Authorization": f"bearer {workflow_task_token}"}
            )
            assert res.status_code == 401, res.text
            assert "token audience validation failed" in res.text

            # fail to use a WORKFLOW task token on a non-WORKFLOW endpoint outside of Fence
            # TODO service other than arborist, where authutils is updated
            # url = f"{pytest.root_url}/authz/mapping"
            # res = requests.get(url, headers={"Authorization": f"bearer {workflow_task_token}"})
            # assert res.status_code == 401, res.text
            # assert "token audience validation failed" in res.text

            # succeed using a WORKFLOW task token on a WORKFLOW endpoint
            res = requests.get(
                f"{DPOP_PROXY_URL}:{proxy_port}/ga4gh/tes/v1/tasks",
                headers={"Authorization": f"bearer {workflow_task_token}"},
            )
            assert res.status_code == 200, res.text

        with get_dpop_task_token("FOO") as (foo_task_token, proxy_port):
            # fail to use a non-WORKFLOW task token on a WORKFLOW endpoint
            url = f"{DPOP_PROXY_URL}:{proxy_port}/ga4gh/tes/v1/tasks"
            res = requests.get(
                url, headers={"Authorization": f"bearer {foo_task_token}"}
            )
            assert res.status_code == 401, "Should not be allowed to list TES tasks"
            assert "token audience validation failed" in res.text

            # succeed using a task token on an Arborist endpoint, regardless of type, since
            # Arborist should accept all tokens for authorization verification purposes
            url = f"{pytest.root_url}/authz/mapping"
            res = requests.get(
                url, headers={"Authorization": f"bearer {foo_task_token}"}
            )
            assert res.status_code == 200, res.text

    def test_denylist_task_token(self):
        """
        TODO
        """
        with get_dpop_task_token() as (task_token, proxy_port):
            # check that the token can be used
            url = f"{DPOP_PROXY_URL}:{proxy_port}/ga4gh/tes/v1/tasks"
            res = requests.get(url, headers={"Authorization": f"bearer {task_token}"})
            assert res.status_code == 200, res.text

            # denylist the token
            self.fence.revoke_token(task_token)

            # the server should now reject the token
            url = f"{DPOP_PROXY_URL}:{proxy_port}/ga4gh/tes/v1/tasks"
            res = requests.get(url, headers={"Authorization": f"bearer {task_token}"})
            assert res.status_code == 403, "Should not be allowed to list TES tasks"

    # TODO rename tests to say "tes" and/or "nextflow"
    @pytest.mark.skipif(
        "funnel" not in pytest.deployed_services,
        reason="funnel service is not running on this environment",
    )
    @pytest.mark.skipif(
        "gen3-workflow" not in pytest.deployed_services,
        reason="gen3-workflow service is not running on this environment",
    )
    @pytest.mark.gen3_workflow
    def test_dpop_proxy(self):
        """
        TODO
        """
        auth = Gen3Auth(
            refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
        )
        with dpop_proxy_context(auth=auth, task_token_type="WORKFLOW") as (
            task_token,
            proxy_port,
        ):
            # url = f"{pytest.root_url}/user/credentials/api/access_token?task_token=WORKFLOW"
            # res = requests.post(url, json={"api_key": pytest.api_keys[user]["api_key"]})
            # assert res.status_code == 200, res.text
            # print(res.json()["access_token"])

            return
            url = f"{pytest.root_url}/ga4gh/tes/v1/tasks"
            res = requests.get(url, headers={"Authorization": f"bearer {task_token}"})
            assert res.status_code == 401, "Should not be allowed to list TES tasks"
            assert res.json().get("error") == "dpop_required"

            config_overrides = [
                "process.container = 'quay.io/nextflow/bash'",  # TODO whitelist it
                f"tes.endpoint = '{DPOP_PROXY_URL}:{proxy_port}/ga4gh/tes'",
                f"tes.oauthToken = '{task_token}'",
                f"aws.accessKey = '{task_token}'",
                f"aws.client.endpoint = '{DPOP_PROXY_URL}:{proxy_port}/s3'",
            ]
            with tempfile.NamedTemporaryFile(delete=True) as config_file:
                config_file.write("\n".join(config_overrides).encode())
                config_file.flush()
                workflow_log = self.gen3_workflow.run_nextflow_workflow(
                    workflow_dir="test_data/gen3_workflow/",
                    workflow_script="hello",  # basic 4-task hello-world workflow
                    nextflow_config_files=["nextflow.config", config_file.name],
                    s3_working_directory=self.s3_storage_config.working_directory,
                    params={"gpu": "true", "run": "TEST_GPU"},
                )

            logger.info(f"Workflow log:")
            completed_tasks = []
            for line in workflow_log.splitlines():
                logger.info(line)
                if "Task completed > TaskHandler" in line:
                    completed_tasks.append(nextflow_parse_completed_line(line))

            for task_name, task in nextflow_parse_completed_tasks(
                completed_tasks
            ).items():
                assert (
                    task["status"] == "COMPLETED"
                ), f"Task '{task_name}' failed with status: {task['status']}"
                assert (
                    task["exit_code"] == "0"
                ), f"Task '{task_name}' returned exit code {task['exit_code']}"
