/*
  String parameter NAMESPACE
    e.g., qa-anvil

  String parameter SERVICE
    e.g., sheepdog, indexd
  This is to help roll a specific service pod

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
        stage('Create Expired Token') {
            options {
                    timeout(time: 5, unit: 'MINUTES')   // timeout on this stage
                }
            steps {
                dir("create-expired-token") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh

                            # Create expired token
                            g3kubectl exec $(gen3 pod \$SERVICE \$NAMESPACE) -- fence-create token-create --scopes openid,user,fence,data,credentials,google_service_account,google_credentials --type access_token --exp \$EXPIRATION --username \$USERNAME > expired_token.txt
                            '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'create-expired-token/expired_token.txt'
        }
    }
}
