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
                dir("clean-up-indices"){
                    sh '''#!/bin/bash +x
                    set -e
                    export GEN3_HOME=\$WORKSPACE/cloud-automation
                    export KUBECTL_NAMESPACE=\${NAMESPACE}
                    source $GEN3_HOME/gen3/gen3setup.sh

                    # get etlmapping names
                    etlMappingNames=$(g3kubectl get cm etl-mapping -o jsonpath='{.data.etlMapping\\.yaml}' | yq '.mappings[].name' | xargs)
                    IFS=' ' read -r -a aliases <<< "$etlMappingNames"

                    # Add the "-array-config" suffix to each element
                    for etlMappingName in "${aliases[@]}"; do
                        aliases+=("${etlMappingName}_0" "${etlMappingName}-array-config" "${etlMappingName}-array-config_0")
                    done

                    echo "${aliases[@]}"
                    for alias in ${aliases[@]}; do
                        gen3 es port-forward > /dev/null 2>&1
                        sleep 5s
                        # checking if an alias exists
                        exists=${curl -I -s $ESHOST/_alias/${alias} /dev/null 2>&1 | grep HTTP/ | tail -1 | awk '{print $2}'}
                        if grep -q "HTTP/1.1 200 OK" <<< "$exists"; then
                        if [[ $exists = "HTTP/1.1 200 OK"* ]]; then
                            #do the delete part
                        else
                            echo "Alias not found"
                        fi

                        curl -X DELETE -s $ESHOST/${alias} > /dev/null 2>&1
                        if [[ $? -eq 0 ]]
                        then
                            echo "${alias}_0 successfully deleted"
                        else
                            echo "${alias}_0 not deleted successfully"

                        # checking if an alias exists
                        curl -I -s $ESHOST/_alias/${alias} /dev/null 2>&1
                        if [[ $? -eq 0  ]];then
                            echo "${alias} exists"
                        else
                            echo "${alias} doesnot exist"
                        fi
                    done
                    '''
                }
            }
        }
    }
}
