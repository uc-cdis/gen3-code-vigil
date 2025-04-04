#!/bin/bash
# Make sure to run the below command on a seperate window for the curl commands to work
# kubectl port-forward service/gen3-elasticsearch-master 9200:9200

# Create pfbexport_subject_1 indices
curl -iv -X PUT "localhost:9200/pfbexport_subject_1" -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@index_data/subject_mapping.json"
curl -X POST localhost:9200/_aliases -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@index_data/subject_alias.json"
curl -H 'Content-Type: application/x-ndjson' "localhost:9200/pfbexport_subject_1/subject/_bulk" --data-binary @index_data/subject_batch.ndjson

# Create pfbexport_file_1 indices
curl -iv -X PUT "localhost:9200/pfbexport_file_1" -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@index_data/file_mapping.json"
curl -X POST localhost:9200/_aliases -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@index_data/file_alias.json"
curl -H 'Content-Type: application/x-ndjson' "localhost:9200/pfbexport_file_1/subject/_bulk" --data-binary @index_data/file_batch.ndjson

# Create pfbexport_config_1 indices
curl -iv -X PUT "localhost:9200/pfbexport_configs_1" -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@index_data/array_mapping.json"
curl -X POST localhost:9200/_aliases -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@index_data/configs_alias.json"
