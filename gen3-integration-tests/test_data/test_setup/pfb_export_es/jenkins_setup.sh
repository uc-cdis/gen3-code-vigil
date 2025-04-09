#!/bin/bash
#
# See https://www.elastic.co/guide/en/elasticsearch/reference/6.8/docs-bulk.html

gen3 es create pfbexport_subject_1 index_data/subject_mapping.json
gen3 es alias pfbexport_subject_1 pfbexport_subject_alias
curl -H 'Content-Type: application/x-ndjson' "${ESHOST}/pfbexport_subject_1/subject/_bulk" --data-binary @index_data/subject_batch.ndjson

gen3 es create pfbexport_file_1 index_data/file_mapping.json
gen3 es alias pfbexport_file_1 pfbexport_file_alias
curl -H 'Content-Type: application/x-ndjson' "${ESHOST}/pfbexport_file_1/file/_bulk" --data-binary @index_data/file_batch.ndjson

gen3 es create pfbexport_configs_1 index_data/array_mapping.json
gen3 es alias pfbexport_configs_1 pfbexport_configs_alias
