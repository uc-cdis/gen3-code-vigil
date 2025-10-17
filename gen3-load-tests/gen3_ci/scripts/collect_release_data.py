import csv
import json
import os
from datetime import datetime

folder_path = "/Users/krishnaa/planx/gen3-code-vigil/gen3-load-tests/test_data/json"
output_csv = "output.csv"
csv_fields = [
    "run_date",
    "run_num",
    "release_version",
    "test_suite",
    "test_case",
    "result",
    "checks_fails",
    "checks_passes",
    "checks_value",
    "http_req_duration_avg",
    "http_req_duration_min",
    "http_req_duration_med",
    "http_req_duration_max",
    "http_req_duration_p90",
    "http_req_duration_p95",
    "data_sent_count",
    "data_sent_rate",
    "iterations_count",
    "iterations_rate",
]

rows = []

for filename in os.listdir(folder_path):
    if filename.endswith(".json"):
        file_path = os.path.join(folder_path, filename)
        try:
            start_time = datetime.now().strftime("%m-%d-%Y")
            with open(file_path, "r", encoding="utf-8") as f:
                output = json.load(f)
            test_suite = {
                "fence-presigned-url.json": "TestFencePresignedURL",
                "ga4gh-drs-performance.json": "TestGa4ghDrsPerformance",
                "indexd-create-indexd-records.json": "TestIndexdCreateRecords",
                "indexd-drs-endpoint.json": "TestIndexdDrsEndpoint",
                "metadata-service-create-and-query.json": "TestMetadataCreateAndQuery",
                "metadata-service-filter-large-database.json": "TestMetadataFilterLargeDatabase",
                "sheepdog-import-clinical-metadata.json": "TestSheepdogImportClinicalMetadata",
            }
            test_case = {
                "fence-presigned-url.json": "test_fence_presigned_url",
                "ga4gh-drs-performance.json": "test_ga4gh_drs_performance",
                "indexd-create-indexd-records.json": "test_indexd_create_indexd_records",
                "indexd-drs-endpoint.json": "test_indexd_drs_endpoint",
                "metadata-service-create-and-query.json": "test_metadata_service_create_and_query",
                "metadata-service-filter-large-database.json": "test_metadata_service_filter_large_database",
                "sheepdog-import-clinical-metadata.json": "test_sheepdog_import_clinical_metadata",
            }
            row = {
                "run_date": str(start_time),
                "run_num": 101,
                "release_version": "2025.01",
                "test_suite": test_suite[filename],
                "test_case": test_case[filename],
                "result": "passed",
                "checks_fails": output.get("metrics", {})
                .get("checks", {})
                .get("fails"),
                "checks_passes": output.get("metrics", {})
                .get("checks", {})
                .get("passes"),
                "checks_value": output.get("metrics", {})
                .get("checks", {})
                .get("value"),
                "http_req_duration_avg": output["metrics"]["http_req_duration"]["avg"],
                "http_req_duration_min": output["metrics"]["http_req_duration"]["min"],
                "http_req_duration_med": output["metrics"]["http_req_duration"]["med"],
                "http_req_duration_max": output["metrics"]["http_req_duration"]["max"],
                "http_req_duration_p90": output["metrics"]["http_req_duration"][
                    "p(90)"
                ],
                "http_req_duration_p95": output["metrics"]["http_req_duration"][
                    "p(95)"
                ],
                "data_sent_count": output["metrics"]["data_sent"]["count"],
                "data_sent_rate": output["metrics"]["data_sent"]["rate"],
                "iterations_count": output["metrics"]["iterations"]["count"],
                "iterations_rate": output["metrics"]["iterations"]["rate"],
            }
            rows.append(row)

        except json.JSONDecodeError as e:
            print(f"JSON error in {filename}: {e}")
        except Exception as e:
            print(f"Error processing {filename}: {e}")

with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=csv_fields)
    writer.writeheader()
    writer.writerows(rows)

print(f"\nExtracted data written to '{output_csv}'")
