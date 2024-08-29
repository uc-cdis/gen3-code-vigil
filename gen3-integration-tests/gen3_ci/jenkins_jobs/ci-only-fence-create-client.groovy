/*
    String parameter NAMESPACE
        e.g. jenkins-blood

    Artifact archived - client_creds.txt
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


                        # CLIENT_NAME,USER_NAME,CLIENT_TYPE,ARBORIST_POLICIES,EXPIRES_IN
                        client_details=(
                            "basic-test-client,test-client@example.com,basic,None,"
                            "implicit-test-client,test@example.com,implicit,None,"
                            "basic-test-abc-client,test-abc-client@example.com,basic,None,"
<<<<<<< HEAD:gen3-integration-tests/gen3_ci/jenkins_jobs/ci-only-fence-create-client.groovy
<<<<<<< HEAD:gen3-integration-tests/gen3_ci/jenkins_jobs/ci-only-fence-create-client.groovy
                            "jenkinsClientTester,dcf-integration-test-0@planx-pla.net,client_credentials,None,"
                            "jenkins-client-no-expiration,test-user,client_credentials,None,"
                            "jenkins-client-short-expiration,test-user,client_credentials,None,0.00000000001"
                            "jenkins-client-medium-expiration,test-user,client_credentials,None,4"
                            "jenkins-client-long-expiration,test-user,client_credentials,None,30"
                            "ras-test-client,UCtestuser128,basic,programs.QA-admin programs.test-admin programs.DEV-admin programs.jnkns-admin,"
=======
                            "jenkins-client-tester,dcf-integration-test-0@planx-pla.net,client_credentials,None,"
=======
                            "jenkinsClientTester,dcf-integration-test-0@planx-pla.net,client_credentials,None,"
>>>>>>> 879e4d9 (fix the code):gen3-integration-tests/gen3_ci/jenkins_jobs/fence-create-client.groovy
                            "jenkins-client-no-expiration,test-user,client_credentials,None,"
                            "jenkins-client-short-expiration,test-user,client_credentials,None,0.00000000001"
                            "jenkins-client-medium-expiration,test-user,client_credentials,None,4"
                            "jenkins-client-long-expiration,test-user,client_credentials,None,30"
>>>>>>> d89cf66 (add new code to support pytest.clients dict):gen3-integration-tests/gen3_ci/jenkins_jobs/fence-create-client.groovy
                        )

                        combined='{}'
                        for value in "${client_details[@]}"; do
                            # Split the variable into an array using comma as the delimiter
                            IFS=',' read -r CLIENT_NAME USER_NAME CLIENT_TYPE ARBORIST_POLICIES EXPIRES_IN <<< "${value}"
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
                                *)
                                    FENCE_CMD="${FENCE_CMD} --client ${CLIENT_NAME} --user ${USER_NAME} --urls https://${NAMESPACE}.planx-pla.net"
                            esac

                            if [[ -n $EXPIRES_IN ]]; then
                                FENCE_CMD="${FENCE_CMD} --expires-in ${EXPIRES_IN}"
                            fi

                            echo "Running: ${FENCE_CMD}"
                            # execute the above fence command
                            # execute the above fence command
                            FENCE_CMD_RES=$(bash -c "${FENCE_CMD}")

                            echo "CLIENT_NAME: ${CLIENT_NAME} ${FENCE_CMD_RES}" >> clients_creds.txt
                        done

                        # Run usersync
                        gen3 job run usersync ADD_DBGAP true
                        g3kubectl wait --for=condition=complete --timeout=-1s jobs/usersync
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'create-fence-client/clients_creds.txt'
        }
    }
}