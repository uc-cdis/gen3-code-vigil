import allure

from allure_commons.types import AttachmentType


def screenshot(page, file_name):
    allure.attach(
        page.screenshot(full_page=True),
        name=file_name,
        attachment_type=AttachmentType.PNG,
    )
