/*
    String parameter NAMESPACE
        e.g. jenkins-blood

    Artifact archived - clients_creds.txt
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
                dir("ci-only-create-fence-client"){
                    script {
                        sh '''#!/bin/bash +x
                        set -e
                        export GEN3_HOME=\$WORKSPACE/cloud-automation
                        export KUBECTL_NAMESPACE=\${NAMESPACE}
                        source $GEN3_HOME/gen3/gen3setup.sh


                        # CLIENT_NAME,USER_NAME,CLIENT_TYPE,ARBORIST_POLICIES,EXPIRES_IN,SCOPES
                        client_details=(
                            "basic-test-client,test-client@example.com,basic,None,"
                            "implicit-test-client,test@example.com,implicit,None,"
                            "basic-test-abc-client,test-abc-client@example.com,basic,None,"
                            "jenkins-client-tester,dcf-integration-test-0@planx-pla.net,client_credentials,None,"
                            "jenkins-client-no-expiration,test-user,client_credentials,None,"
                            "jenkins-client-short-expiration,test-user,client_credentials,None,0.00000000001"
                            "jenkins-client-medium-expiration,test-user,client_credentials,None,4"
                            "jenkins-client-long-expiration,test-user,client_credentials,None,30"
                            "ras-test-client,UCtestuser128,basic,programs.QA-admin programs.test-admin programs.DEV-admin programs.jnkns-admin,"
                            "ras-test-client1,UCtestuser127,auth_code,programs.QA-admin programs.test-admin programs.DEV-admin programs.jnkns-admin,,openid user data google_credentials ga4gh_passport_v1"
                            "ras-test-client2,UCtestuser129,auth_code,programs.QA-admin programs.test-admin programs.DEV-admin programs.jnkns-admin,,openid user data google_credentials"
                        )

                        combined='{}'
                        for value in "${client_details[@]}"; do
                            # Split the variable into an array using comma as the delimiter
                            IFS=',' read -r CLIENT_NAME USER_NAME CLIENT_TYPE ARBORIST_POLICIES EXPIRES_IN SCOPES<<< "${value}"
                            echo "Creating client: ${CLIENT_NAME}"

                            DELETE_CMD="kubectl -n $KUBECTL_NAMESPACE exec $(gen3 pod fence) -- fence-create client-delete --client ${CLIENT_NAME}"
                            echo "Running: ${DELETE_CMD}"
                            bash -c "${DELETE_CMD}"

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
                                "auth_code")
                                    FENCE_CMD="${FENCE_CMD} --client ${CLIENT_NAME} --user ${USER_NAME} --urls https://${NAMESPACE}.planx-pla.net --grant-types authorization_code"
                                    ;;
                                *)
                                    FENCE_CMD="${FENCE_CMD} --client ${CLIENT_NAME} --user ${USER_NAME} --urls https://${NAMESPACE}.planx-pla.net"
                            esac

                            if [[ -n $EXPIRES_IN ]]; then
                                FENCE_CMD="${FENCE_CMD} --expires-in ${EXPIRES_IN}"
                            fi

                            if [[ -n $SCOPES ]]; then
                                FENCE_CMD="${FENCE_CMD} --allowed-scopes ${SCOPES}"
                            fi

                            echo "Running: ${FENCE_CMD}"
                            # execute the above fence command
                            # execute the above fence command
                            FENCE_CMD_RES=$(bash -c "${FENCE_CMD}" | tee >(awk -v prefix="$CLIENT_NAME" 'END{print prefix ":" $0}' >> clients_creds.txt))
                        done

                        # Run usersync
                        gen3 job run usersync ADD_DBGAP true
                        kubectl wait --for=condition=complete --timeout=-1s jobs/usersync
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'ci-only-create-fence-client/clients_creds.txt'
        }
    }
}
