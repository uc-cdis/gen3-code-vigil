from contextlib import ExitStack, contextmanager

import pytest
from gen3.auth import Gen3Auth
from gen3.dpop import dpop_proxy_context
from utils import logger


def get_token_and_gen3_url(user: str = "main_account", suffix=""):
    """
    Returns:
        tuple (access token, Gen3 URL)
    """
    gen3_url = pytest.root_url

    if not user:
        return None, f"{gen3_url}{suffix}"

    auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=gen3_url)
    access_token = auth.get_access_token()
    return access_token, f"{gen3_url}{suffix}"


@contextmanager
def get_dpop_bound_task_token(
    token_type, user="main_account", expires_in=3600, expected_status_code=200
):
    """
    Use the Gen3 SDK's DPoP proxy to obtain a DPoP-bound task token from Fence.
    This requires `DPOP_ENABLED: true` in the Fence configuration.

    Returns:
        tuple (task token, proxy URL)

    Usage:
        with get_dpop_bound_task_token("WORKFLOW") as (task_token, proxy_url):
            url = f"{proxy_url}/..."
            res = requests.get(url, headers={"Authorization": f"bearer {task_token}"})
    """
    auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=pytest.root_url)
    token, url = None, None
    with ExitStack() as stack:
        try:
            task_token, proxy_port = stack.enter_context(
                dpop_proxy_context(
                    auth=auth,
                    task_token_type=token_type,
                    task_token_expiration=expires_in,
                )
            )
            token, url = task_token, f"http://127.0.0.1:{proxy_port}"
        except Exception as e:
            if expected_status_code == 200:
                logger.error(
                    f"Unable to get a '{token_type}' task token for '{user}': {e}"
                )
                raise
            assert f"[{expected_status_code}]" in str(e)
        yield token, url
