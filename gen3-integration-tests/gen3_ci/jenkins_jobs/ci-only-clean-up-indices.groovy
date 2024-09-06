/*
    String parameter NAMESPACE
    e.g. qa-dcp
*/
pipeline {
    agent {
        node {
            label 'gen3-ci-worker'
        }
    }
    stages {
        stage('Clean Up Workspace') {
            steps {
                cleanWs()
            }
        }
        stage('Initial Setup') {
            steps {
                // cloud-automation
                checkout([
                  $class: 'GitSCM',
                  branches: [[name: 'refs/heads/master']],
                  doGenerateSubmoduleConfigurations: false,
                  extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: 'cloud-automation']],
                  submoduleCfg: [],
                  userRemoteConfigs: [[credentialsId: 'PlanXCyborgUserJenkins', url: 'https://github.com/uc-cdis/cloud-automation.git']]
                ])
            }
        }
        stage('Clean Up Indices') {
            steps {
                dir("ci-only-clean-up-indices"){
                    sh '''#!/bin/bash +x
                    set -e
                    export GEN3_HOME=\$WORKSPACE/cloud-automation
                    export KUBECTL_NAMESPACE=\${NAMESPACE}
                    source $GEN3_HOME/gen3/gen3setup.sh

                    # get etlmapping names
                    etlMappingNames=$(kubectl get cm etl-mapping -o jsonpath='{.data.etlMapping\\.yaml}' -n ${KUBECTL_NAMESPACE} | yq '.mappings[].name' | xargs)
                    IFS=' ' read -r -a indices <<< "$etlMappingNames"

                    # Add the "-array-config" suffix to each element
                    for etlMappingName in "${indices[@]}"; do
                        indices+=("${etlMappingName}-array-config")
                    done
                    # output - qa-dcp_etl qa-dcp_file qa-dcp_etl-array-config qa-dcp_file-array-config

                    echo "${indices[@]}"
                    for index in "${indices[@]}"; do
                        # port-forward to talk to elastic search
                        gen3 es port-forward > /dev/null 2>&1
                        sleep 5s

                        # will loop through the indices array and delete the zeroth index
                        # qa-dcp_etl_0 qa-dcp_file_0 qa-dcp_etl-array-config_0 qa-dcp_file-array-config_0
                        # deleting index_0 and checking if successfully deleted
                        echo "Deleting index ${index} ..."
                        delete_index0_ouput=$(curl -X DELETE -s $ESHOST/${index}_0 | jq '.acknowledged' )
                        if [[ "$delete_index0_ouput" = "true"  ]]; then
                            echo "${index}_0 deleted successfully"
                        else
                            echo "${index}_0 not deleted successfully"
                        fi
                    done
                    # check if there are other indices associated with etlMappingName
                    all_indices=$(curl -s -X GET "$ESHOST/_cat/indices" | grep $KUBECTL_NAMESPACE | awk '{print $3}'  | xargs)
                    for i in $all_indices; do
                        echo "Deleting index ${i} ..."
                        delete_indices=$(curl -X DELETE -s $ESHOST/${i} | jq '.acknowledged')
                        if [[ "$delete_indices" = "true"  ]]; then
                            echo "${i} deleted successfully"
                        else
                            echo "${i} not deleted successfully"
                        fi
                    done
                    '''
                }
            }
        }
    }
}
