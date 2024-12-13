/*
    String parameter NAMESPACE
        e.g. jenkins-blood
    String parameter USERNAME
        e.g. dummy-one@example.org
    String parameter EMAIL
        e.g. main@example.org

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
                  branches: [[name: "chore/fence_deploy_azlinux"]],
                  doGenerateSubmoduleConfigurations: false,
                  extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: 'cloud-automation']],
                  submoduleCfg: [],
                  userRemoteConfigs: [[credentialsId: 'PlanXCyborgUserJenkins', url: 'https://github.com/uc-cdis/cloud-automation.git']]
                ])
            }
        }
        stage('Force Link Google Account') {
            steps {
                dir("ci-only-force_link_google"){
                    script {
                        sh '''#!/bin/bash +x
                        set -e
                        export GEN3_HOME=\$WORKSPACE/cloud-automation
                        export KUBECTL_NAMESPACE=\${NAMESPACE}
                        source \$GEN3_HOME/gen3/gen3setup.sh

                        LINK_CMD="kubectl -n $KUBECTL_NAMESPACE exec $(gen3 pod fence) -- fence-create force-link-google --username ${USERNAME} --google-email ${EMAIL}"
                        echo "Running: ${LINK_CMD}"
                        LINK_CMD_RES=$(bash -c "${LINK_CMD}")
                        '''
                    }
                }
            }
        }
    }
}
