# 🧹 `cleanup_google_resources.py`

This script performs automated cleanup of Google Cloud service accounts, Google Bucket Access groups, and IAM policy bindings on the QA Cloud Storage buckets based on a prefix match. Each time a PR runs the Helm CI Pipeline, GCP resources are generated, so this script was created to regularily cleanup these resources as Fence does not currently have the functionlity to delete them.

## 🔧 Configuration

Update the following variables at the top of the script:

- `PROJECT_ID`: GCP project containing service accounts and buckets.
- `PREFIX_TO_DELETE`: String prefix (e.g., `"ci"`) to match service accounts, groups, or IAM principals.
- `DRY_RUN`: Set to `True` to simulate deletions without applying changes.
- `ADMIN_EMAIL`: Super admin email for delegated access to Google Bucket Access groups.

## 🔍 What It Does

### 1. `delete_old_sas()`

- Lists all GCP service accounts in the project.
- Identifies those whose email starts with the given prefix.
- Deletes matching service accounts unless `DRY_RUN` is enabled.

### 2. `delete_old_groups()`

- Authenticates to the Google Admin SDK using a service account and admin delegation.
- Lists all Google Bucket Access groups in the organization.
- Deletes any groups whose email starts with the prefix.
- Honors `DRY_RUN` to only print what would be deleted.

### 3. `delete_bucket_principals_with_prefix(bucket_name)`

- Fetches IAM policy for the specified GCS bucket.
- Identifies IAM bindings where members (groups only) start with the prefix.
- Removes those principals and updates the bucket policy unless `DRY_RUN` is enabled.

## 📝 Example Usage

This script is deployed as a Cloud Run Job in Google Cloud Platform and is scheduled to run daily at 12:00 AM UTC. If updates are ever needed or the job needs to be redeployed, follow the steps below to configure and redeploy it correctly.

### 1. Create a Service Account

In the GCP Console:

```bash
# Assign required roles to the service account
roles/iam.serviceAccountAdmin
roles/storage.admin
```

---

### 2. Create and Upload Secret Key

Generate a key for the service account and download the JSON file. Then upload it to Secret Manager:

```bash
gcloud secrets create service-account-creds \
  --data-file="<path-to-local-secrets-file>.json"
```

Grant the service account access to this secret:

```bash
gcloud secrets add-iam-policy-binding service-account-creds \
  --member="serviceAccount:<service-account-name>" \
  --role="roles/secretmanager.secretAccessor"
```

---

### 3. Create Docker Artifact Repository

This will hold the Docker image used in the Cloud Run Job:

```bash
gcloud artifacts repositories create ci-automated-cleanup \
  --repository-format=docker \
  --location=us-east1 \
  --description="Repo for Cleanup Image to be used in Cloud Run Job"
```

---

### 4. Build and Push Docker Image

From the directory containing your `Dockerfile` and `requirements.txt`:

```bash
gcloud builds submit \
  --tag us-east1-docker.pkg.dev/<project-id>/ci-automated-cleanup/cleaner
```

---

### 5. Deploy the Cloud Run Job

```bash
gcloud run jobs deploy ci-automated-cleanup \
  --tasks 1 \
  --set-env-vars SLEEP_MS=10000,FAIL_RATE=0.1 \
  --max-retries 5 \
  --region us-east1 \
  --project=<project-id> \
  --service-account=<service-account-name> \
  --image=us-east1-docker.pkg.dev/<project-id>/ci-automated-cleanup/cleaner \
  --set-secrets=SA_KEY=service-account-creds:latest
```

---

### 6. Schedule the Job

In the GCP Console:

1. Navigate to **Cloud Run > Jobs**
2. Find your `ci-automated-cleanup` job
3. Click **Edit**
4. Open the **Triggers** tab
5. Set up a **cron schedule** (e.g., `0 0 * * *` for 12:00 AM UTC)

---

## 🔐 Admin Access Configuration

### 7. Grant Admin User Access to Service Account

```bash
gcloud iam service-accounts add-iam-policy-binding <service-account-name> \
  --member="user:<gcp-admin-user-email>" \
  --role="roles/iam.serviceAccountUser"
```

---

### 8. Register Client ID in Admin Console

1. Go to [admin.google.com](https://admin.google.com)
2. Navigate to:
   **Security > API Controls > Domain-wide Delegation**
3. Click **Manage Domain-wide Delegation**
4. Click **Add new** and enter:
   - **Client ID**: (from the GCP Console's service account details)
   - **OAuth Scopes**:
     ```
     https://www.googleapis.com/auth/admin.directory.group
     ```

---

## ⚠️ Important Notes

- The `ADMIN_EMAIL` passed to the script **must**:
  - Belong to a user in the Admin Console
  - Have the role `roles/serviceusage.serviceUsageConsumer`
  - Have **Groups Admin** privileges
