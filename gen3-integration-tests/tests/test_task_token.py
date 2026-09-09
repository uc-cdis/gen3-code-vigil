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
"""

import time

# import gen3
from gen3.auth import Gen3Auth
from gen3.dpop import dpop_proxy_context, resolve_service_endpoints
import jwt
import pytest
import requests
import tempfile

from services.fence import Fence
from services.gen3workflow import Gen3Workflow, WorkflowStorageConfig, nextflow_parse_completed_line, nextflow_parse_completed_tasks
from utils import logger


# TODO rename or comment: non-dpop
def get_task_token(
    type="WORKFLOW", user="main_account", expires_in=3600, expected_status_code=200
):
    url = f"{pytest.root_url}/user/credentials/api/access_token?task_token={type}&expires_in={expires_in}"
    res = requests.post(url, json={"api_key": pytest.api_keys[user]["api_key"]})
    assert res.status_code == expected_status_code, res.text
    if res.status_code == 200:
        return res.json()["access_token"]


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
        cls.s3_storage_config = WorkflowStorageConfig.from_dict(cls.gen3_workflow.setup_storage())

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
        # TODO something else than arborist
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

        # TODO succeed using a WORKFLOW task token on an Arborist endpoint, since Arborist should
        # accept all tokens for authz verification purposes
        # See https://cdis.slack.com/archives/C02SH3UB2T0/p1785954635381709?thread_ts=1785953406.385109&cid=C02SH3UB2T0

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
    def test_dpop_proxy(self): #, mock_auth_endpoint):
        """
        TODO
        """
        # from gen3.auth import Gen3Auth
        auth = Gen3Auth(refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url)
        # auth = self.gen3_workflow._get_auth_module()
        # print('auth.endpoint', auth.endpoint)
        # print(
        #     "endpoint_from_token",
        #     gen3.auth.endpoint_from_token(pytest.api_keys["main_account"]["api_key"]),
        # )  # should be localhost.....

        # resolved_tes_endpoint, resolved_s3_endpoint = resolve_service_endpoints(auth)
        with dpop_proxy_context(auth=auth, task_token_type="WORKFLOW") as (task_token, proxy_port):
            config_overrides = f"""process.container = 'public.ecr.aws/docker/library/alpine:latest'
tes.endpoint = 'http://127.0.0.1:{proxy_port}/ga4gh/tes'
tes.oauthToken = '{task_token}'
aws.accessKey = '{task_token}'
aws.client.endpoint = 'http://127.0.0.1:{proxy_port}/s3'"""
            with tempfile.NamedTemporaryFile(delete=True) as config_file:
                config_file.write(config_overrides.encode())
                config_file.flush()
                workflow_log = self.gen3_workflow.run_nextflow_workflow(
                    workflow_dir="test_data/gen3_workflow/",
                    workflow_script="hello",
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

            for task_name, task in nextflow_parse_completed_tasks(completed_tasks).items():
                print(task_name)



            # env = os.environ.copy()
            # env["GEN3_DPOP_BOUND_TASK_TOKEN"] = task_token
            # env["GEN3_DPOP_PROXY_PORT"] = str(proxy_port)

            # with contextlib.ExitStack() as stack:
            #     args = list(nf_args)
            #     if generate_config:
            #         # The config outlives nothing: the directory goes away with the run.
            #         directory = stack.enter_context(tempfile.TemporaryDirectory())
            #         config_path = _write_proxy_config(
            #             directory=directory,
            #             proxy_port=proxy_port,
            #             tes_endpoint=resolved_tes_endpoint,
            #             s3_endpoint=resolved_s3_endpoint,
            #         )
            #         args += ["-c", config_path]
            #         logger.info(f"Generated Nextflow config: {config_path}")

            #     logger.info("*** Starting Nextflow run... ***")
            #     try:
            #         result = subprocess.run(
            #             ["nextflow", "run"] + args, env=env, check=False
            #         )
            #     except FileNotFoundError:
            #         logger.error(
            #             "Could not find `nextflow` on your PATH. Install it and try again."
            #         )
            #         raise
            #     logger.info("*** Completed Nextflow run! ***")
            #     return result.returncode




        # with dpop_proxy_context(auth=auth, task_token_type="WORKFLOW") as (
        #     task_token,
        #     proxy_port,
        # ):
        #     # Anything sent to 127.0.0.1:{proxy_port} is signed and forwarded.
        #     print("task_token from proxy:", task_token)
        #     url = f"{pytest.root_url}/ga4gh/tes/v1/tasks"
        #     res = requests.get(
        #         url, headers={"Authorization": f"bearer {task_token}"}
        #     )
        #     assert res.status_code == 200, res.text
        #     # print(res.text)
