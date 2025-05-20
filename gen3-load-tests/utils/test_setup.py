import csv
import json
import random
from pathlib import Path

import pytest
import requests
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission
from jinja2 import Environment, FileSystemLoader
from utils import TEST_DATA_PATH_OBJECT, logger


def get_api_key(user):
    file_path = Path.home() / ".gen3" / f"{pytest.namespace}_{user}.json"
    try:
        api_key_json = json.loads(file_path.read_text())
    except FileNotFoundError:
        logger.error(f"API key file not found: '{file_path}'")
        raise
    return api_key_json


def get_users():
    user_list_path = TEST_DATA_PATH_OBJECT / "test_setup" / "users.csv"
    with open(user_list_path) as f:
        users = {row["USER_ID"]: row["EMAIL"] for row in csv.DictReader(f)}
    return users


def get_indexd_records(auth, indexd_record_acl=None):
    url = f"{pytest.root_url}/index/index"
    if indexd_record_acl:
        url += f"?acl={indexd_record_acl}"
    result = requests.get(url=url, auth=auth)
    assert (
        result.status_code == 200
    ), f"Expected status 200 but got {result.status_code}"
    return result.json()["records"]


def perform_pre_load_testing_setup():
    auth = Gen3Auth(
        refresh_token=pytest.api_keys["main_account"], endpoint=pytest.root_url
    )
    create_program(auth, "DEV")
    create_program(auth, "phs000178")
    create_program(auth, "jnkns")
    create_project(auth, "DEV", "test")
    create_project(auth, "jnkns", "jenkins")
    create_project(auth, "jnkns", "jenkins2")


def create_program(auth, program_name):
    submission = Gen3Submission(auth_provider=auth)
    if f"/v0/submission/{program_name}" not in submission.get_programs()["links"]:
        program_record = {
            "type": "program",
            "name": program_name,
            "dbgap_accession_number": program_name,
        }
        submission.create_program(program_record)


def create_project(auth, program_name, project_name):
    submission = Gen3Submission(auth_provider=auth)
    if (
        f"/v0/submission/{program_name}/{project_name}"
        not in submission.get_projects(program_name)["links"]
    ):
        project_record = {
            "type": "project",
            "code": project_name,
            "name": project_name,
            "dbgap_accession_number": project_name,
        }
        submission.create_project(program_name, project_record)


def generate_random_values():
    return {
        "submitted_sample_id": str(random.randint(10000, 50000)),
        "biosample_id": str(random.randint(0, 50000)).zfill(6),
        "dbgap_sample_id": str(random.randint(10000, 50000)),
        "sra_sample_id": str(random.randint(10000, 50000)),
        "submitted_subject_id": str(random.randint(0, 99999)).zfill(5),
        "study_subject_id": str(random.randint(0, 999999)).zfill(6),
        "study_version": str(random.randint(0, 99999)),
        "dbgap_subject_id": str(random.randint(0, 9999999)).zfill(7),
        "consent_code": str(random.randint(1, 4)).zfill(1),
        "gender": random.choice(["male", "female"]),
        "guid_type": random.choice(["indexed_file_object", "metadata_object"]),
    }


def generate_metadata_templates(num_of_jsons):
    template_path = (
        TEST_DATA_PATH_OBJECT / "metadata_service_template" / "template.json"
    )
    generated_templates_path = (
        TEST_DATA_PATH_OBJECT / "generated_metadata_service_template"
    )
    generated_templates_path.mkdir(parents=True, exist_ok=True)

    env = Environment(loader=FileSystemLoader(template_path.parent))

    # Load the template file
    template = env.get_template(template_path.name)

    for i in range(num_of_jsons):
        random_values = generate_random_values()
        rendered_json = template.render(**random_values)
        record = json.loads(rendered_json)

        # Save directly using i as part of filename
        filename = f"{generated_templates_path}/{i+1}.json"
        with open(filename, "w") as file:
            json.dump(record, file, indent=4)
