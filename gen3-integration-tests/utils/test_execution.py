import allure

from allure_commons.types import AttachmentType

from utils.misc import retry


def screenshot(page, file_name):
    allure.attach(
        page.screenshot(timeout=0, full_page=True),
        name=file_name,
        attachment_type=AttachmentType.PNG,
    )


@retry(2, 30, exceptions=(AssertionError))
def assert_with_retry(operation, expected, actual, error_prefix):
    if operation == "equals":
        assert (
            expected == actual
        ), f"{error_prefix}: expected - {expected}, actual - {actual}"
