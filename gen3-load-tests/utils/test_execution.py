import allure
from allure_commons.types import AttachmentType
from utils import LOAD_TESTING_OUTPUT_PATH


def attach_output_file(file_name):
    ext = file_name.split(".")[-1]
    attachment_types = {"json": AttachmentType.JSON, "txt": AttachmentType.TEXT}
    assert ext in attachment_types
    with open((LOAD_TESTING_OUTPUT_PATH / file_name), "r") as file:
        allure.attach(
            file.read(), name=file_name, attachment_type=attachment_types[ext]
        )
