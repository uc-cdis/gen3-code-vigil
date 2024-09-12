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
        stage('Check Indices After ETL') {
            steps {
                dir("ci-only-check-indices-after-etl"){
                    sh '''#!/bin/bash +x
                    set -e
                    export GEN3_HOME=\$WORKSPACE/cloud-automation
                    export KUBECTL_NAMESPACE=\${NAMESPACE}
                    source $GEN3_HOME/gen3/gen3setup.sh

                    etlMappingNames=$(kubectl get cm etl-mapping -o jsonpath='{.data.etlMapping\\.yaml}' -n ${KUBECTL_NAMESPACE} | yq '.mappings[].name' | xargs)
                    IFS=' ' read -r -a aliases <<< "$etlMappingNames"

                    echo "${aliases[@]}"
                    for alias in "${aliases[@]}"; do
                        # port-forward to talk to elastic search
                        gen3 es port-forward > /dev/null 2>&1
                        sleep 5s

                        # checking if the alias exists
                        exists=$(curl -I -s "$ESHOST/_alias/${alias}" 2>&1 | grep HTTP/ | tail -1 | awk '{print $2}')
                        if [[ $exists == "200" ]]; then
                            echo "${alias} is present"
                        fi

                        # getting the index from the alias
                        indexAlias=$(curl -X GET -s "$ESHOST/_alias/${alias}" | jq '. | keys[0]'  | xargs)

                        # check if the index number has increased
                        version="${indexAlias##*_}"
                        if [[ $version == "1" ]]; then
                            echo "Index version has increased"
                        fi
                    done
                    '''
                }
            }
        }
    }
}
