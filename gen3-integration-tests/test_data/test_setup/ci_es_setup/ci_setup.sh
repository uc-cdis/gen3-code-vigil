#!/bin/bash
# Make sure to run the below command on a seperate window for the curl commands to work
# kubectl port-forward service/gen3-elasticsearch-master 9200:9200
namespace=$1

kubectl port-forward service/gen3-elasticsearch-master 9200:9200 -n ${namespace} &
port_forward_pid=$!
sleep 10  # Give port-forward some time to start

# Create ci_imaging_study_1 indices
curl -iv -X PUT "localhost:9200/ci_imaging_study_1" -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@test_data/test_setup/ci_es_setup/index_data/imaging_study_mapping.json"
curl -X POST localhost:9200/_aliases -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@test_data/test_setup/ci_es_setup/index_data/imaging_study_alias.json"
curl -H 'Content-Type: application/x-ndjson' "localhost:9200/ci_imaging_study_1/imaging_study/_bulk" --data-binary @test_data/test_setup/ci_es_setup/index_data/imaging_study_batch.ndjson

# Create ci_subject_1 indices
curl -iv -X PUT "localhost:9200/ci_subject_1" -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@test_data/test_setup/ci_es_setup/index_data/subject_mapping.json"
curl -X POST localhost:9200/_aliases -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@test_data/test_setup/ci_es_setup/index_data/subject_alias.json"
curl -H 'Content-Type: application/x-ndjson' "localhost:9200/ci_subject_1/subject/_bulk" --data-binary @test_data/test_setup/ci_es_setup/index_data/subject_batch.ndjson

# Create ci_file_1 indices
curl -iv -X PUT "localhost:9200/ci_file_1" -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@test_data/test_setup/ci_es_setup/index_data/file_mapping.json"
curl -X POST localhost:9200/_aliases -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@test_data/test_setup/ci_es_setup/index_data/file_alias.json"
curl -H 'Content-Type: application/x-ndjson' "localhost:9200/ci_file_1/subject/_bulk" --data-binary @test_data/test_setup/ci_es_setup/index_data/file_batch.ndjson

# Create ci_config_1 indices
curl -iv -X PUT "localhost:9200/ci_configs_1" -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@test_data/test_setup/ci_es_setup/index_data/array_mapping.json"
curl -X POST localhost:9200/_aliases -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@test_data/test_setup/ci_es_setup/index_data/configs_alias.json"

kill $port_forward_pid
