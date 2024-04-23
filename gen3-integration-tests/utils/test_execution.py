import allure

from allure_commons.types import AttachmentType


def screenshot(page, file_name):
    allure.attach(
        page.screenshot(timeout=0, full_page=True),
        name=file_name,
        attachment_type=AttachmentType.PNG,
    )
