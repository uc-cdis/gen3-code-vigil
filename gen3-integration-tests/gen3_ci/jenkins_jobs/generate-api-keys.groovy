/*
    This Jenkins job will help generate api keys for test users on given Target environment

    String parameter NAMESPACE
        e.g., qa-anvil

    Artifact archived - {NAMESPACE}_main_account.json, {NAMESPACE}_indexing_account.json
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
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh
                            echo "creating main_account api key for \$NAMESPACE"
                            gen3 api api-key cdis.autotest@gmail.com > \${NAMESPACE}_main_account.json

                            echo "creating indexing_account for \$NAMESPACE"
                            gen3 api api-key ctds.indexing.test@gmail.com > \${NAMESPACE}_indexing_account.json

                            echo "creating auxAcct1 for \$NAMESPACE"
                            gen3 api api-key dummy-one@planx-pla.net > \${NAMESPACE}_auxAcct1_account.json

                            echo "creating auxAcct2 for \$NAMESPACE"
                            gen3 api api-key smarty-two@planx-pla.net > \${NAMESPACE}_auxAcct2_account.json

                            echo "creating user0 for \$NAMESPACE"
                            gen3 api api-key dcf-integration-test-0@planx-pla.net > \${NAMESPACE}_user0_account.json

                           echo "creating user2 for \$NAMESPACE"
                            gen3 api api-key dcf-integration-test-2@planx-pla.net > \${NAMESPACE}_user2_account.json
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
