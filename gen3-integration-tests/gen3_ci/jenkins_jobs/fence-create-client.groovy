/*
    String parameter CLIENT_NAME
        e.g. jenkinsClientTester
    String parameter USER_NAME
        e.g. dcf-integration-test-0@planx-pla.net
    String parameter CLIENT_TYPE
        e.g. client_credentials or implicit
    String parameter ARBORIST_POLICIES
        e.g. NONE
    String parameter EXPIRES_IN
        e.g. NONE

    Artifact archived -
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
        stage('Create Fence Client') {
            steps {
                dir("create-fence-client"){
                    script {
                        sh '''#!/bin/bash +x
                        set -e
                        export GEN3_HOME=\$WORKSPACE/cloud-automation
                        export KUBECTL_NAMESPACE=\${NAMESPACE}
                        source $GEN3_HOME/gen3/gen3setup.sh

                        # construct fence-create command depending on the parameters provided by the run
                        FENCE_CMD="kubectl -n $KUBECTL_NAMESPACE exec $(gen3 pod fence) -- fence-create"
                        echo "${FENCE_CMD}"

                        if [ -n "$ARBORIST_POLICIES" ]; then
                            FENCE_CMD="${FENCE_CMD} client-create --policies ${ARBORIST_POLICIES}"
                        else
                            FENCE_CMD="${FENCE_CMD} client-create"
                        fi

                        case "$CLIENT_TYPE" in
                            "client_credentials")
                                FENCE_CMD="${FENCE_CMD} --client ${CLIENT_NAME} --grant-types client_credentials"
                                ;;
                            "implicit")
                                FENCE_CMD="${FENCE_CMD} --client ${CLIENT_NAME} --user ${USER_NAME} --urls https://${NAMESPACE}.planx-pla.net --grant-types implicit --public"
                                ;;
                            *)
                                FENCE_CMD="${FENCE_CMD} --client ${CLIENT_NAME} --user ${USER_NAME} --urls https://${NAMESPACE}.planx-pla.net"
                        esac

                        if [[ -n $EXPIRES_IN ]]; then
                            FENCE_CMD="${FENCE_CMD} --expires-in ${EXPIRES_IN}"
                        fi

                        echo "Running: ${FENCE_CMD}"
                        # execute the above fence command
                        FENCE_CMD_RES=$(bash -c "${FENCE_CMD}" | tee >(tail -n 1 > client_creds.txt))
                        case "$CLIENT_TYPE" in
                            "implicit")
                                sed -n 's/.*(\\x27\\(.*\\)\\x27, \\(None\\)).*/\\1\\n\\2/p' client_creds.txt > temp_client_creds.txt
                                ;;
                            *)
                                sed -n 's/.*\\x27\\([^\\x27]*\\)\\x27,\\s*\\x27\\([^\\x27]*\\)\\x27.*/\\1\\n\\2/p' client_creds.txt > temp_client_creds.txt
                        esac
                        mv temp_client_creds.txt client_creds.txt
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'create-fence-client/client_creds.txt'
        }
    }
}
