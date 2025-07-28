import json
import os
import urllib

import requests
from google.auth import default
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from googleapiclient import discovery
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

PROJECT_ID = ""
PREFIX_TO_DELETE = "ci"
DRY_RUN = False  # Set to False to actually delete service accounts
ADMIN_EMAIL = ""
SCOPES = ["https://www.googleapis.com/auth/admin.directory.group"]


def delete_old_sas():
    credentials, _ = default()
    service = discovery.build("iam", "v1", credentials=credentials)

    service_accounts = []
    page_token = None

    while True:
        request = (
            service.projects()
            .serviceAccounts()
            .list(name=f"projects/{PROJECT_ID}", pageToken=page_token)
        )

        response = request.execute()
        accounts = response.get("accounts", [])
        service_accounts.extend(accounts)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    print(f"Found {len(service_accounts)} service accounts")

    for sa in service_accounts:
        email = sa["email"]
        if email.startswith(PREFIX_TO_DELETE):
            if DRY_RUN:
                print(f"[Dry Run] Would delete: {email}")
            else:
                print(f"Deleting: {email}")
                service.projects().serviceAccounts().delete(
                    name=f"projects/{PROJECT_ID}/serviceAccounts/{email}"
                ).execute()


def delete_old_groups():
    key_dict = json.loads(os.environ["SA_KEY"])
    creds = service_account.Credentials.from_service_account_info(
        key_dict, scopes=SCOPES
    ).with_subject(ADMIN_EMAIL)

    creds.refresh(Request())

    headers = {
        "Authorization": f"Bearer {creds.token}",
        "x-goog-user-project": PROJECT_ID,
    }

    groups = []
    page_token = None

    while True:
        params = {"customer": "my_customer", "maxResults": 200}
        if page_token:
            params["pageToken"] = page_token

        response = requests.get(
            "https://admin.googleapis.com/admin/directory/v1/groups",
            headers=headers,
            params=params,
        )
        if response.status_code != 200:
            print(f"Failed to list groups: {response.status_code} - {response.text}")
            return

        data = response.json()
        groups.extend(data.get("groups", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    matching_groups = [g for g in groups if g["email"].startswith(PREFIX_TO_DELETE)]
    print(f"Found {len(matching_groups)} groups with prefix '{PREFIX_TO_DELETE}'")

    for group in matching_groups:
        group_email = group["email"]
        group_id = group["id"]

        if DRY_RUN:
            print(f"[Dry Run] Would delete group: {group_email}")
        else:
            del_response = requests.delete(
                f"https://admin.googleapis.com/admin/directory/v1/groups/{group_id}",
                headers=headers,
            )
            if del_response.status_code == 204:
                print(f"Deleted group: {group_email}")
            else:
                print(
                    f"Failed to delete {group_email}: {del_response.status_code} - {del_response.text}"
                )


def delete_bucket_principals_with_prefix(bucket_name):
    credentials, _ = default()
    storage = build("storage", "v1", credentials=credentials)
    # Get current IAM policy
    policy = storage.buckets().getIamPolicy(bucket=bucket_name).execute()
    bindings = policy.get("bindings", [])

    bindings_to_change = {}
    new_policy = policy
    new_policy["bindings"] = []
    for binding in bindings:
        updated_members = []
        members = binding["members"]
        bindings_to_change[binding["role"]] = []
        for m in members:
            mem = m.replace("deleted:", "")
            if mem.startswith(f"group:{PREFIX_TO_DELETE}"):
                bindings_to_change[binding["role"]].append(m)
            else:
                updated_members.append(m)
        new_binding = binding
        new_binding["members"] = updated_members
        new_policy["bindings"].append(new_binding)

    print(f"Checking IAM bindings for bucket: {bucket_name}\n")

    changes_detected = False
    # bindings_to_change = {'ObjectViewer': ['group:ci1', 'group:ci2'], 'ObjectWriter': ['group:ci1', 'group:ci2']}
    for role, bindings_to_remove in bindings_to_change.items():
        num_bindings_to_remove = len(bindings_to_remove)
        if num_bindings_to_remove > 0:
            print(f"{role} will remove {num_bindings_to_remove} bindings: ")
            for b in bindings_to_remove:
                print(b)
            changes_detected = True
    print(f"changes detected: {changes_detected}")

    if DRY_RUN:
        print("\n✅ Dry Run!")
        if changes_detected:
            print("New policy would have been:")
            print(new_policy)
            print("\n\n" + "-" * 50)
    else:

        print("\n🔐 Applying policy changes...")

        try:
            storage.buckets().setIamPolicy(
                bucket=bucket_name, body=new_policy
            ).execute()
            print("✅ Bucket policy updated.")
        except Exception as e:
            print("❌ Failed to set IAM policy:")
            print(str(e))
            print("Attempted policy body:", json.dumps(new_policy, indent=2))
            raise


if __name__ == "__main__":
    delete_old_sas()
    delete_old_groups()
    delete_bucket_principals_with_prefix("bucket1")
    delete_bucket_principals_with_prefix("bucket2")
