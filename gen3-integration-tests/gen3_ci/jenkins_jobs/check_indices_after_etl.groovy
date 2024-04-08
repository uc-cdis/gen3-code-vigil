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
                dir("check-indices-after-etl"){
                    sh '''#!/bin/bash +x
                    set -e
                    export GEN3_HOME=\$WORKSPACE/cloud-automation
                    export KUBECTL_NAMESPACE=\${NAMESPACE}
                    source $GEN3_HOME/gen3/gen3setup.sh

                    etlMappingNames=$(g3kubectl get cm etl-mapping -o jsonpath='{.data.etlMapping\\.yaml}' | yq '.mappings[].name' | xargs)

                    '''
                }
            }
        }
    }
}
