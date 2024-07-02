/*
  String parameter NAMESPACE
    e.g., jenkins-dcp

*/
pipeline {
    agent {
        node {
            label 'gen3-ci-worker'
        }
    }
    stages {
        stage('Clean old workspace') {
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
        stage('get Study-Viewer Index') {
            steps {
                dir("get-study-viewer-index"){
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh

                            INDEX=$(gen3 secrets decode portal-config gitops.json | jq '.studyViewerConfig[].dataType' | tr -d '"')
                            echo $INDEX > study_viewer_index.txt
                        '''
                        }
                    }
                }
            }
        }
    post {
        always {
            archiveArtifacts artifacts: 'get-study-viewer-index/study_viewer_index.txt'
        }
    }
}
