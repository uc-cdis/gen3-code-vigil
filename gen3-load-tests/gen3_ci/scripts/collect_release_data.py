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
                "embedding-bulk-content-retieval-medium[1-500].json": "TestGen3EmbeddingBulkRetrievalMedium",
                "embedding-bulk-content-retieval-medium[1-1000].json": "TestGen3EmbeddingBulkRetrievalMedium",
                "embedding-bulk-content-retieval-medium[1-2000].json": "TestGen3EmbeddingBulkRetrievalMedium",
                "embedding-bulk-content-retieval-medium[2-500].json": "TestGen3EmbeddingBulkRetrievalMedium",
                "embedding-bulk-content-retieval-medium[2-1000].json": "TestGen3EmbeddingBulkRetrievalMedium",
                "embedding-bulk-content-retieval-medium[2-2000].json": "TestGen3EmbeddingBulkRetrievalMedium",
                "embedding-bulk-content-retieval-medium[3-500].json": "TestGen3EmbeddingBulkRetrievalMedium",
                "embedding-bulk-content-retieval-medium[3-1000].json": "TestGen3EmbeddingBulkRetrievalMedium",
                "embedding-bulk-content-retieval-medium[3-2000].json": "TestGen3EmbeddingBulkRetrievalMedium",
                "embedding-bulk-content-retieval-small[1-500].json": "TestGen3EmbeddingBulkRetrievalSmall",
                "embedding-bulk-content-retieval-small[1-1000].json": "TestGen3EmbeddingBulkRetrievalSmall",
                "embedding-bulk-content-retieval-small[1-2000].json": "TestGen3EmbeddingBulkRetrievalSmall",
                "embedding-bulk-content-retieval-small[2-500].json": "TestGen3EmbeddingBulkRetrievalSmall",
                "embedding-bulk-content-retieval-small[2-1000].json": "TestGen3EmbeddingBulkRetrievalSmall",
                "embedding-bulk-content-retieval-small[2-2000].json": "TestGen3EmbeddingBulkRetrievalSmall",
                "embedding-bulk-content-retieval-small[3-500].json": "TestGen3EmbeddingBulkRetrievalSmall",
                "embedding-bulk-content-retieval-small[3-1000].json": "TestGen3EmbeddingBulkRetrievalSmall",
                "embedding-bulk-content-retieval-small[3-2000].json": "TestGen3EmbeddingBulkRetrievalSmall",
                "embedding-publish-embedding-gen3sdk[expr-10000-256].json": "TestGen3EmbeddingPublishEmbeddings",
                "embedding-publish-embedding-gen3sdk[hist-10000-1536].json": "TestGen3EmbeddingPublishEmbeddings",
                "embedding-search-embedding-unknown-collection[5-cosine-similarity].json": "TestGen3EmbeddingSearchUnKnownCollection",
                "embedding-search-embedding-unknown-collection[5-l1-distance].json": "TestGen3EmbeddingSearchUnKnownCollection",
                "embedding-search-embedding-unknown-collection[5-inner-product].json": "TestGen3EmbeddingSearchUnKnownCollection",
                "embedding-search-embedding-unknown-collection[10-cosine-similarity].json": "TestGen3EmbeddingSearchUnKnownCollection",
                "embedding-search-embedding-unknown-collection[5-l1-distance].json": "TestGen3EmbeddingSearchUnKnownCollection",
                "embedding-search-embedding-unknown-collection[5-inner-product].json": "TestGen3EmbeddingSearchUnKnownCollection",
                "embedding-search-embedding-known-collection[5-cosine-similarity].json": "TestGen3EmbeddingSearchKnownCollection",
                "embedding-search-embedding-known-collection[5-l1-distance].json": "TestGen3EmbeddingSearchKnownCollection",
                "embedding-search-embedding-known-collection[5-inner-product].json": "TestGen3EmbeddingSearchKnownCollection",
                "embedding-search-embedding-known-collection[10-cosine-similarity].json": "TestGen3EmbeddingSearchKnownCollection",
                "embedding-search-embedding-known-collection[5-l1-distance].json": "TestGen3EmbeddingSearchKnownCollection",
                "embedding-search-embedding-known-collection[5-inner-product].json": "TestGen3EmbeddingSearchKnownCollection",
            }
            test_case = {
                "fence-presigned-url.json": "test_fence_presigned_url",
                "ga4gh-drs-performance.json": "test_ga4gh_drs_performance",
                "indexd-create-indexd-records.json": "test_indexd_create_indexd_records",
                "indexd-drs-endpoint.json": "test_indexd_drs_endpoint",
                "metadata-service-create-and-query.json": "test_metadata_service_create_and_query",
                "metadata-service-filter-large-database.json": "test_metadata_service_filter_large_database",
                "sheepdog-import-clinical-metadata.json": "test_sheepdog_import_clinical_metadata",
                "embedding-bulk-content-retieval-medium[1-500].json": "test_embedding_bulk_content_retieval_medium[1-500]",
                "embedding-bulk-content-retieval-medium[1-1000].json": "test_embedding_bulk_content_retieval_medium[1-1000]",
                "embedding-bulk-content-retieval-medium[1-2000].json": "test_embedding_bulk_content_retieval_medium[2-1000]",
                "embedding-bulk-content-retieval-medium[2-500].json": "test_embedding_bulk_content_retieval_medium[2-500]",
                "embedding-bulk-content-retieval-medium[2-1000].json": "test_embedding_bulk_content_retieval_medium[2-1000]",
                "embedding-bulk-content-retieval-medium[2-2000].json": "test_embedding_bulk_content_retieval_medium[2-2000]",
                "embedding-bulk-content-retieval-medium[3-500].json": "test_embedding_bulk_content_retieval_medium[3-500]",
                "embedding-bulk-content-retieval-medium[3-1000].json": "test_embedding_bulk_content_retieval_medium[3-1000]",
                "embedding-bulk-content-retieval-medium[3-2000].json": "test_embedding_bulk_content_retieval_medium[3-2000]",
                "embedding-bulk-content-retieval-small[1-500].json": "test_embedding_bulk_content_retrieval_small[1-500]",
                "embedding-bulk-content-retieval-small[1-1000].json": "test_embedding_bulk_content_retrieval_small[1-1000]",
                "embedding-bulk-content-retieval-small[1-2000].json": "test_embedding_bulk_content_retrieval_small[1-2000]",
                "embedding-bulk-content-retieval-small[2-500].json": "test_embedding_bulk_content_retrieval_small[2-500]",
                "embedding-bulk-content-retieval-small[2-1000].json": "test_embedding_bulk_content_retrieval_small[2-1000]",
                "embedding-bulk-content-retieval-small[2-2000].json": "test_embedding_bulk_content_retrieval_small[2-2000]",
                "embedding-bulk-content-retieval-small[3-500].json": "test_embedding_bulk_content_retrieval_small[3-500]",
                "embedding-bulk-content-retieval-small[3-1000].json": "test_embedding_bulk_content_retrieval_small[3-1000]",
                "embedding-bulk-content-retieval-small[3-2000].json": "test_embedding_bulk_content_retrieval_small[3-2000]",
                "embedding-publish-embedding-gen3sdk[expr-10000-256].json": "test_embedding_publish_embedding_gen3sdk[expr-10000-256]",
                "embedding-publish-embedding-gen3sdk[hist-10000-1536].json": "test_embedding_publish_embedding_gen3sdk[hist-10000-1536]",
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
