/*
   String parameter NAMESPACE
   e.g., qa-anvil

  String parameter CLOUD_AUTO_BRANCH
    e.g., master
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
                  branches: [[name: "refs/heads/${params.CLOUD_AUTO_BRANCH}"]],
                  doGenerateSubmoduleConfigurations: false,
                  extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: 'cloud-automation']],
                  submoduleCfg: [],
                  userRemoteConfigs: [[credentialsId: 'PlanXCyborgUserJenkins', url: 'https://github.com/uc-cdis/cloud-automation.git']]
                ])
            }
        }
        stage('Check Register Users On') {
            options {
                    timeout(time: 5, unit: 'MINUTES')   // timeout on this stage
                }
            steps {
                dir("ci-only-check-register-users-on"){
                    script {
                        sh '''#!/bin/bash +x
                        set -e
                        export GEN3_HOME=\$WORKSPACE/cloud-automation
                        export KUBECTL_NAMESPACE=\${NAMESPACE}
                        source $GEN3_HOME/gen3/gen3setup.sh

                        gen3 secrets decode fence-config | grep REGISTER_USERS_ON > register_users_on.txt || true
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'ci-only-check-register-users-on/register_users_on.txt'
        }
    }
}
