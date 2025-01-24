#!/bin/bash
#
# See https://www.elastic.co/guide/en/elasticsearch/reference/6.8/docs-bulk.html
#

gen3 es create jenkins_imaging_study index_data/imaging_study_mapping.json
gen3 es alias jenkins_imaging_study_1 jenkins_imaging_study_alias
curl -H 'Content-Type: application/x-ndjson' "${ESHOST}/jenkins_imaging_study_1/imaging_study/_bulk" --data-binary @index_data/imaging_study_batch.ndjson
