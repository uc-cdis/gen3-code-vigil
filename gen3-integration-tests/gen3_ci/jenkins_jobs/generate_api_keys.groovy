/*
    This Jenkins job will help generate api keys for test users on given Target environment

    String parameter TARGET_ENVIRONMENT
        e.g., qa-anvil

    Artifact archived - {TARGET_ENVIRONMENT}_main_account.json, {TARGET_ENVIRONMENT}_indexing_account.json
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
        stage('Initial setup') {
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
        stage('Generate API Key') {
            steps {
                dir("generate-api-key") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${TARGET_ENVIRONMENT}
                            source $GEN3_HOME/gen3/gen3setup.sh
                            echo "creating main_account api key for \$TARGET_ENVIRONMENT"
                            gen3 api api-key cdis.autotest@gmail.com > \${TARGET_ENVIRONMENT}_main_account.json

                            echo "creating indexing_account for \$TARGET_ENVIRONMENT"
                            gen3 api api-key ctds.indexing.test@gmail.com > \${TARGET_ENVIRONMENT}_indexing_account.json
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'generate-api-key/*.json'
        }
    }
}
