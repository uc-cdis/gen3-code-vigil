#!/bin/bash
# Make sure to run the below command on a seperate window for the curl commands to work
# kubectl port-forward service/gen3-elasticsearch-master 9200:9200

# Create jenkins_imaging_study_1 indices
curl -iv -X PUT "localhost:9200/jenkins_imaging_study_1" -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@index_data/imaging_study_mapping.json"
curl -X POST localhost:9200/_aliases -H 'Content-Type: application/json' -H 'Accept: application/json' "-d@index_data/imaging_study_alias.json"
curl -H 'Content-Type: application/x-ndjson' "localhost:9200/jenkins_imaging_study_1/imaging_study/_bulk" --data-binary @index_data/imaging_study_batch.ndjson
