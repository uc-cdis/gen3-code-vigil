import os

import yaml

# Get all environment variables
TARGET_ENV = os.getenv("TARGET_ENV")
RELEASE_VERSION = os.getenv("IMAGE_TAG_VERSION")
GEN3_GITOPS_PATH = os.getenv("GEN3_GITOPS_PATH")
GEN3_HELM_PATH = os.getenv("GEN3_HELM_PATH")
THOR_REPO_LIST_PATH = os.getenv("THOR_REPO_LIST_PATH")
TARGET_ENV_PATH = f"{GEN3_GITOPS_PATH}/{TARGET_ENV}"
GEN3_DEFAULT_VALUES_PATH = f"{GEN3_HELM_PATH}/helm/gen3/values.yaml"
REPO_LIST = []
REPO_DICT = {
    "pelican": "pelican-export",
    "docker-nginx": "revproxy",
    "gen3-fuse": "gen3fuse-sidecar",
    "cloud-automation": "awshelper",
    "ACCESS-backend": "access-backend",
    "cdis-data-client": "gen3-client",
    "data-portal": "portal",
    "audit-service": "audit",
    "metadata-service": "metadata",
    "gen3-spark": "etl",
    "tube": "etl",
    "workspace-token-service": "wts",
    "indexs3client": "ssjdispatcher",
}
CURRENT_REPO_DICT_KEY = ""


class MyDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(MyDumper, self).increase_indent(flow, False)


def update_version_for_service(service_name, target_file):
    with open(target_file, "r") as f:
        target_file_config = yaml.safe_load(f)
    with open(GEN3_DEFAULT_VALUES_PATH, "r") as gen3_f:
        gen3_helm_config = yaml.safe_load(gen3_f)
    # If service is disabled in incoming manifest, don't update anything
    if target_file_config[service_name].get("enabled") is False:
        print(f"{service_name} enabled is set to False")
        return
    # If service is enabled in incoming or default manifest then update
    if target_file_config[service_name].get("enabled") or gen3_helm_config[
        service_name
    ].get("enabled"):
        print(f"Updated {CURRENT_REPO_DICT_KEY} in {target_file}")
        # Handle update for tube and spark
        if service_name == "etl":
            if "image" not in target_file_config[service_name]:
                target_file_config[service_name]["image"] = {}
                target_file_config[service_name]["image"]["tube"] = {}
                target_file_config[service_name]["image"]["spark"] = {}
            target_file_config[service_name]["image"]["tube"]["tag"] = RELEASE_VERSION
            target_file_config[service_name]["image"]["spark"]["tag"] = RELEASE_VERSION
        else:
            if "image" not in target_file_config[service_name]:
                target_file_config[service_name]["image"] = {}
            target_file_config[service_name]["image"]["tag"] = RELEASE_VERSION
        # Handle indexs3client update
        if service_name == "ssjdispatcher":
            print("Updating ssjdispatcher['indexing']")
            target_file_config[service_name][
                "indexing"
            ] = f"quay.io/cdis/indexs3client:{RELEASE_VERSION}"
        # Handle sowerConfig update
        if service_name == "sower":
            print("Updating sowerConfig")
            sower_config = target_file_config.get("sower", {}).get("sowerConfig", [])
            for job in sower_config:
                container = job.get("container")
                if container and "image" in container:
                    quay_link = container["image"].split(":")[0]
                    container["image"] = f"{quay_link}:{RELEASE_VERSION}"
        # write the updates back to yaml file
        with open(target_file, "w") as f:
            yaml.dump(
                target_file_config,
                f,
                Dumper=MyDumper,
                default_flow_style=False,
                sort_keys=False,
            )


# Read the THOR_REPO_LIST_PATH and add it to a list
with open(THOR_REPO_LIST_PATH, "r") as f:
    for line in f:
        stripped = line.strip()
        if stripped:
            REPO_LIST.append(stripped)

# Update version for each service from REPO_LIST
for service_name in REPO_LIST:
    # Set this to use for printing purposes
    CURRENT_REPO_DICT_KEY = service_name
    # Check if {service_name} in REPO_DICT and change the service name
    if service_name in REPO_DICT:
        service_name = REPO_DICT[service_name]

    service_file = f"{TARGET_ENV_PATH}/values/{service_name}.yaml"
    values_file = f"{TARGET_ENV_PATH}/values/values.yaml"

    # Check if {service_name}.yaml exists
    if os.path.exists(service_file):
        print(f"Found {service_name}.yaml")
        update_version_for_service(service_name, service_file)
    else:
        with open("values.yaml", "r") as f:
            values_config = yaml.safe_load(f)
        # Check if {service_name} in values.yaml
        if service_name in values_config:
            print(f"Found {service_name} in values.yaml")
            update_version_for_service(service_name, values_file)
        else:
            print(f"Skipping update for {service_name}")
