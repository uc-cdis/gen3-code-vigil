#!/bin/bash
#
# See https://www.elastic.co/guide/en/elasticsearch/reference/6.8/docs-bulk.html
#

gen3 es create ci_imaging_study_1 test_data/test_setup/ci_es_setup/index_data/imaging_study_mapping.json
gen3 es alias ci_imaging_study_1 ci_imaging_study_alias
curl -H 'Content-Type: application/x-ndjson' "${ESHOST}/ci_imaging_study_1/imaging_study/_bulk" --data-binary @test_data/test_setup/ci_es_setup/index_data/imaging_study_batch.ndjson

gen3 es create ci_subject_1 test_data/test_setup/ci_es_setup/index_data/subject_mapping.json
gen3 es alias ci_subject_1 ci_subject_alias
curl -H 'Content-Type: application/x-ndjson' "${ESHOST}/ci_subject_1/subject/_bulk" --data-binary @test_data/test_setup/ci_es_setup/index_data/subject_batch.ndjson

gen3 es create ci_file_1 test_data/test_setup/ci_es_setup/index_data/file_mapping.json
gen3 es alias ci_file_1 ci_file_alias
curl -H 'Content-Type: application/x-ndjson' "${ESHOST}/ci_file_1/file/_bulk" --data-binary @test_data/test_setup/ci_es_setup/index_data/file_batch.ndjson

gen3 es create ci_configs_1 test_data/test_setup/ci_es_setup/index_data/array_mapping.json
gen3 es alias ci_configs_1 ci_configs_alias
