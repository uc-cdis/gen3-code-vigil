#!/bin/bash
# Create jenkins_subject_1 indices
curl -iv -X PUT "localhost:9200/jenkins_subject_1" -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@es_indexes_data/subject_mapping.json"
curl -X POST localhost:9200/_aliases -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@es_indexes_data/subject_alias.json"
curl -H 'Content-Type: application/x-ndjson' "localhost:9200/jenkins_subject_1/subject/_bulk" --data-binary @es_indexes_data/subject_batch.ndjson

# Create jenkins_file_1 indices
curl -iv -X PUT "localhost:9200/jenkins_file_1" -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@es_indexes_data/file_mapping.json"
curl -X POST localhost:9200/_aliases -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@es_indexes_data/file_alias.json"
curl -H 'Content-Type: application/x-ndjson' "localhost:9200/jenkins_file_1/subject/_bulk" --data-binary @es_indexes_data/file_batch.ndjson

# Create jenkins_config_1 indices
curl -iv -X PUT "localhost:9200/jenkins_configs_1" -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@es_indexes_data/array_mapping.json"
curl -X POST localhost:9200/_aliases -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@es_indexes_data/configs_alias.json"
