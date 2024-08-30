/*
    String parameter CLIENT_NAME
        e.g. jenkinsClientTester
    String parameter EXPIRES_IN
        e.g. NONE
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
        stage('Fence Client Rotation') {
            steps {
                dir("fence-client-rotate"){
                    script {
                        sh '''#!/bin/bash +x
                        set -e
                        export GEN3_HOME=\$WORKSPACE/cloud-automation
                        export KUBECTL_NAMESPACE=\${NAMESPACE}
                        source $GEN3_HOME/gen3/gen3setup.sh
                        # construct fence-create command depending on the parameters provided by the run
                        FENCE_CMD="kubectl -n $KUBECTL_NAMESPACE exec $(gen3 pod fence) -- fence-create client-rotate --client ${CLIENT_NAME}"
                        echo "${FENCE_CMD}"
                        if [[ -n $EXPIRES_IN ]]; then
                            FENCE_CMD="${FENCE_CMD} --expires-in ${EXPIRES_IN}"
                        fi
                        echo "Running: ${FENCE_CMD}"
                        # execute the above fence command
                        FENCE_CMD_RES=$(bash -c "${FENCE_CMD}" | tee >(tail -n 1 > client_rotate_creds.txt))
                        sed -n 's/.*\\x27\\([^\\x27]*\\)\\x27,\\s*\\x27\\([^\\x27]*\\)\\x27.*/\\1\\n\\2/p' client_rotate_creds.txt > temp_client_creds.txt
                        mv temp_client_creds.txt client_rotate_creds.txt
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'fence-client-rotate/client_rotate_creds.txt'
        }
    }
}
