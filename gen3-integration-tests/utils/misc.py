import os
import time

from cdislogging import get_logger
from filelock import Timeout, FileLock

from utils import TEST_DATA_PATH_OBJECT


logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def one_worker_only(func):
    """
    Use this decorator to make sure only 1 worker runs a function. Other workers will wait until the 1st
    worker is done before proceeding. Useful for configuration autorun fixtures that must run before the
    tests can run.

    Usage:
        @pytest.fixture(autouse=True, scope="session")
        @one_worker_only
        def setup_tests():
            pass
    """

    def run_with_lock():
        worker_id = os.environ["PYTEST_XDIST_WORKER"]
        lock_path = TEST_DATA_PATH_OBJECT / "lock"

        lock = FileLock(lock_path, timeout=0)
        try:  # attempt to get a lock on the lock file
            lock.acquire()
            try:
                logger.info(f"Worker '{worker_id}' running '{func.__name__}'")
                result = func()
                # if `func` completes quickly, this worker may release the lock before other workers
                # attempt to lock, and `func` could run more than once. Wait 1 sec to avoid this
                time.sleep(1)
                logger.info(f"Worker '{worker_id}' is done running '{func.__name__}'")
            finally:
                lock.release()
            return result
        except Timeout:  # unable to lock: another worker already locked; wait
            logger.info(
                f"Worker '{worker_id}' waiting for '{func.__name__}' to be done running"
            )
            with open(lock_path, "r") as lock_file:
                max_it = 10
                for i in range(max_it):
                    try:
                        lock.acquire()
                        # the worker obtained the lock, so `func` is done running => exit
                        lock.release()
                        logger.info(f"Worker '{worker_id}' is done waiting")
                        break
                    except IOError:
                        wait_secs = 3
                        logger.info(f"Worker '{worker_id}' waiting {wait_secs}s...")
                        time.sleep(wait_secs)
                if i == max_it:
                    logger.warn(
                        f"Worker '{worker_id}' waited the max time, '{func.__name__}' is not done running, proceeding anyway"
                    )

    return run_with_lock
