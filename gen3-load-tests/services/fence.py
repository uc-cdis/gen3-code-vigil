from contextlib import ExitStack, contextmanager
from unittest.mock import patch

import pytest
from gen3.auth import (
    Gen3Auth,
    endpoint_from_token,
    remove_trailing_whitespace_and_slashes_in_url,
)
from gen3.dpop import dpop_proxy_context
from utils import logger


class Fence(object):
    # def __init__(self):
    #     # Endpoints
    #     self.BASE_URL = f"{pytest.root_url}/user"
    #     self.ADMIN_FENCE_ENDPOINT = "/admin/user"
    #     self.API_CREDENTIALS_ENDPOINT = "/credentials/api"
    #     self.OAUTH_TOKEN_ENDPOINT = "/oauth2/token"
    #     self.DATA_UPLOAD_ENDPOINT = "/data/upload"
    #     self.DATA_ENDPOINT = "/data"
    #     self.DATA_DOWNLOAD_ENDPOINT = "/data/download"
    #     self.USER_ENDPOINT = "/user"
    #     self.VERSION_ENDPOINT = "/_version"
    #     self.AUTHORIZE_OAUTH2_CLIENT_ENDPOINT = "/oauth2/authorize"
    #     self.TOKEN_OAUTH2_CLIENT_ENDPOINT = "/oauth2/token"
    #     self.MULTIPART_UPLOAD_INIT_ENDPOINT = "/data/multipart/init"
    #     self.MULTIPART_UPLOAD_ENDPOINT = "/data/multipart/upload"
    #     self.MULTIPART_UPLOAD_COMPLETE_ENDPOINT = "/data/multipart/complete"
    #     self.GOOGLE_SA_KEYS_ENDPOINT = "/credentials/google/"
    #     # Locators
    #     self.CONSENT_AUTHORIZE_BUTTON = "//button[@id='yes']"
    #     self.CONSENT_CANCEL_BUTTON = "//button[@id='no']"
    #     self.CONSENT_CODE_ERROR_TEXT = "//div[@class='error-page__status-code-text']/h2"

    @contextmanager
    def get_dpop_bound_task_token(
        self, token_type, user="main_account", expires_in=3600, expected_status_code=200
    ):
        """
        Use the Gen3 SDK's DPoP proxy to obtain a DPoP-bound task token from Fence.
        This requires `DPOP_ENABLED: true` in the Fence configuration.

        Returns:
            tuple (task token, proxy URL)

        Usage:
            with fence.get_dpop_bound_task_token("WORKFLOW") as (task_token, proxy_url):
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

    @contextmanager
    def get_token_and_gen3_url(
        self, user: str = "main_account", use_dpop=False, suffix=""
    ):
        """
        Helper function that patches `Gen3Auth.get_access_token` to allow running tests against a
        local cluster and that uses the SDK's DPoP proxy when needed. Depending on whether DPoP is
        used or not, returns the DPoP proxy URL or the direct URL to the appropriate Gen3 service.

        When running the tests against a local cluster:
        - Fence's `BASE_URL` is set to `http://fence-service.<namespace>.svc.cluster.local`, so
          API keys and access tokens have that as their issuer. This allows other pods in the
          cluster to reach Fence to validate tokens.
        - However, the tests cannot reach this URL from outside the cluster. The cluster is
          exposed at `http://localhost:8000` and that's where the tests can reach Fence to obtain
          access tokens.
        - The SDK's `endpoint_from_token` method extracts the endpoint from the API key. We mock
          this method to return `http://localhost:8000` instead of `http://fence-service.
          <namespace>.svc.cluster.local` so `Gen3Auth` knows to reach Fence there.
        - Note: Setting Fence's `BASE_URL` to `http://localhost:8000` would fix this on the tests
          side, but other pods in the cluster would not be able to reach Fence to validate tokens
          (because within a container, localhost refers to the container itself).
        - Note: This mocking would not work for DPoP-bound tokens, since the URL (`htu`) is
          validated. The most straightforward way around this is to set `DPOP_ENABLED: false` in
          the local cluster's fence and gen3-workflow configs.

        Usage:
            with fence.get_token_and_gen3_url(user, use_dpop=False, suffix="/workflows") as
            (access_token, url):
                resp = requests.get(url, headers={"Authorization": f"bearer {access_token}"})

        Args:
            user (str)
            use_dpop (bool): if True, this function simply proxies to `get_dpop_bound_task_token`.
                If False, it uses the SDK to obtain a generic access token. If False and running in
                a local cluster, the SDK is patched as described above.
            suffix (str): if `use_dpop` is False or the call is anonymous, the returned URL is
                `<Gen3 env URL><suffix>`. If `use_dpop` is True, this parameter is ignored.

        Returns:
            tuple (access token, Gen3 URL)
        """
        gen3_url = pytest.root_url
        is_local_cluster = "localhost" in gen3_url

        if not user:
            yield None, f"{gen3_url}{suffix}"
            return

        if use_dpop:
            if is_local_cluster:
                logger.info(
                    "Running in a local cluster: falling back to a generic non-DPoP token. Warning: this flow requires DPoP to be disabled in fence and gen3-workflow"
                )
            else:
                with self.get_dpop_bound_task_token("WORKFLOW", user) as (
                    access_token,
                    proxy_url,
                ):
                    yield access_token, proxy_url
                    return

        with patch("gen3.auth.endpoint_from_token") as endpoint_from_token_mock:
            auth = Gen3Auth(refresh_token=pytest.api_keys[user], endpoint=gen3_url)
            if is_local_cluster:
                endpoint_from_token_mock.return_value = (
                    remove_trailing_whitespace_and_slashes_in_url(gen3_url)
                )
            else:  # otherwise, no mocking
                endpoint_from_token_mock.side_effect = lambda x: endpoint_from_token(x)

            try:
                access_token = auth.get_access_token()
            except Exception:
                logger.info("Failed to get access token with Gen3Auth")
                raise
            yield access_token, f"{gen3_url}{suffix}"
