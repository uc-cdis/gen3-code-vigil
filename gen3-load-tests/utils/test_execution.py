import allure
from allure_commons.types import AttachmentType
from utils import LOAD_TESTING_OUTPUT_PATH


def attach_json_file(file_name):
    with open((LOAD_TESTING_OUTPUT_PATH / file_name), "r") as file:
        allure.attach(file.read(), name=file_name, attachment_type=AttachmentType.JSON)
