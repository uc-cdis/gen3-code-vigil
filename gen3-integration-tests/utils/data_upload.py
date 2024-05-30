import os
import requests

from cdislogging import get_logger
from utils.misc import retry

logger = get_logger(__name__, log_level=os.getenv("LOG_LEVEL", "info"))


def upload_file_to_s3(presigned_url, file_path, file_size):
    headers = {"Content-Length": str(file_size)}
    response = requests.put(
        url=presigned_url, data=open(file_path, "rb"), headers=headers
    )
    assert (
        response.status_code == 200
    ), f"Upload to S3 didn't happen properly. Status code : {response.status_code}"


@retry(times=12, delay=10, exceptions=(AssertionError))
def wait_upload_file_updated_from_indexd_listener(indexd, file_node):
    response = indexd.get_record(file_node.did)
    indexd.file_equals(res=response, file_node=file_node)
    return response
