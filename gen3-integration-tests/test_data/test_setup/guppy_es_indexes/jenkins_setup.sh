#!/bin/bash
#
# See https://www.elastic.co/guide/en/elasticsearch/reference/6.8/docs-bulk.html
#

#
# Generating the Batch documents:
#
# jq -r -c '.[] | ._source | .auth_resource_path="/programs/jnkns/projects/jenkins"' < subjectData.json | awk '{ print "{ \"index\" : {} }"; print $0; }' | jq -r -c . | tee subjectBatch.njson
# jq -r -c '.hits.hits[] | ._source | .auth_resource_path="/programs/jnkns/projects/jenkins"' < fileData.json | awk '{ print "{ \"index\" : {} }"; print $0; }' | jq -r -c . | tee filesBatch.njson
#

#
# Run the guppy test locally:
#
# GUPPY_FRICKJACK=true RUNNING_LOCAL=true NAMESPACE=reuben npm test -- --verbose --grep '@guppyAPI'
#

# if you're having problems - a little toy for testing
if false; then
  gen3 es create toy_debug_1 es_indexes_data/toy_mapping.json
  curl -H 'Content-Type: application/x-ndjson' "${ESHOST}/toy_debug_1/thing/_bulk" --data-binary @es_indexes_data/toy_batch.ndjson
fi

gen3 es create jenkins_subject_1 es_indexes_data/subject_mapping.json
gen3 es alias jenkins_subject_1 jenkins_subject_alias
curl -H 'Content-Type: application/x-ndjson' "${ESHOST}/jenkins_subject_1/subject/_bulk" --data-binary @es_indexes_data/subject_batch.ndjson

gen3 es create jenkins_file_1 es_indexes_data/file_mapping.json
gen3 es alias jenkins_file_1 jenkins_file_alias
curl -H 'Content-Type: application/x-ndjson' "${ESHOST}/jenkins_file_1/file/_bulk" --data-binary @es_indexes_data/file_batch.ndjson

gen3 es create jenkins_configs_1 es_indexes_data/array_mapping.json
gen3 es alias jenkins_configs_1 jenkins_configs_alias
