import os
import time
import requests
import pytest

from cdislogging import get_logger
from filelock import Timeout, FileLock

from utils import TEST_DATA_PATH_OBJECT
from gen3.auth import Gen3Auth


logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def one_worker_only(wait_secs=3, max_wait_minutes=1):
    """
    Use this decorator to make sure only 1 worker runs a function. Other workers will wait until the 1st
    worker is done before proceeding. Useful for configuration autorun fixtures that must run before the
    tests can run.

    Args:
        wait_secs (int): how long other workers wait between each check.
        max_wait_minutes (int): other workers wait up to `max_wait_minutes` min before giving up and proceeding.

    Usage:
        @pytest.fixture(autouse=True, scope="session")
        @one_worker_only
        def setup_tests():
            pass

        @pytest.fixture(autouse=True, scope="session")
        @one_worker_only(wait_secs=10, max_wait_minutes=15)
        def setup_tests():
            pass
    """

    def one_worker_only_decorator(func):
        def run_with_lock():
            worker_id = os.environ["PYTEST_XDIST_WORKER"]
            lock_path = TEST_DATA_PATH_OBJECT / "lock"

            lock = FileLock(lock_path, timeout=0)
            try:  # attempt to get a lock on the lock file
                lock.acquire()
                try:
                    logger.info(f"Worker '{worker_id}' running '{func.__name__}'")
                    # successful lock: run `func`
                    result = func()
                    # if `func` completes quickly, this worker may release the lock before other workers
                    # attempt to lock, and `func` could run more than once. Wait 1 sec to avoid this
                    time.sleep(0.5)
                    logger.info(
                        f"Worker '{worker_id}' is done running '{func.__name__}'"
                    )
                finally:
                    lock.release()
                return result
            except Timeout:  # unable to lock: another worker already locked; wait
                logger.info(
                    f"Worker '{worker_id}' waiting for '{func.__name__}' to be done running"
                )
                with open(lock_path, "r") as lock_file:
                    waited_secs = 0
                    while True:
                        try:
                            lock.acquire()
                            # the worker obtained the lock, so `func` is done running => exit
                            lock.release()
                            logger.info(f"Worker '{worker_id}' is done waiting")
                            break
                        except IOError:
                            logger.info(f"Worker '{worker_id}' waiting {wait_secs}s...")
                            if waited_secs < max_wait_minutes * 60:
                                time.sleep(wait_secs)
                                waited_secs += wait_secs
                            else:
                                logger.warn(
                                    f"Worker '{worker_id}' waited {max_wait_minutes} min, '{func.__name__}' is not done running, proceeding anyway"
                                )
                                break

        return run_with_lock

    return one_worker_only_decorator


def create_program(program_name, auth_header, user="main_account"):
    auth = Gen3Auth(refresh_token=pytest.api_keys[user])
    program_form = (
        '{"name":"'
        + program_name
        + '","type":"program","dbgap_accession_number":"'
        + program_name
        + '"}'
    )
    response = requests.post(
        url=pytest.root_url + "/api/v0/submission",
        headers=auth_header,
        auth=auth,
        data=program_form,
    )
    if response.status_code == 200:
        logger.info("Successfully Created/Updated program")
    else:
        logger.error("Failed to Create/Update program")


def create_project(project_name, auth_header, user="main_account"):
    auth = Gen3Auth(refresh_token=pytest.api_keys[user])
    project_form = (
        '{"type":"project","code":"'
        + project_name
        + '","name":"jenkins","dbgap_accession_number":"'
        + project_name
        + '","state":"open","releasable":true}'
    )
    response = requests.post(
        url=pytest.root_url + "/api/v0/submission",
        headers=auth_header,
        auth=auth,
        data=project_form,
    )
    if response.status_code == 200:
        logger.info("Successfully Created/Updated project")
    else:
        logger.error("Failed to Create/Update project")
