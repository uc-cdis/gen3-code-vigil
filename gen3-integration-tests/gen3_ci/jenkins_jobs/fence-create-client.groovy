/*
    String parameter NAMESPACE
        e.g. jenkins-blood

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


                        # CLIENT_NAME,USER_NAME,CLIENT_TYPE,ARBORIST_POLICIES,EXPIRES_IN
                        client_details=(
                            "basic-test-client,test-client@example.com,basic,None,"
                            "implicit-test-client,test@example.com,implicit,None,"
                            "basic-test-abc-client,test-abc-client@example.com,basic,None,"
                            "jenkinsClientTester,dcf-integration-test-0@planx-pla.net,client_credentials,None,"
                            "jenkinsClientNoExpiration,test-user,client_credentials,None,"
                            "jenkinsClientShortExpiration,test-user,client_credentials,None,0.00000000001"
                            "jenkinsClientMediumExpiration,test-user,client_credentials,None,4"
                            "jenkinsClientLongExpiration,test-user,client_credentials,None,30"
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
                            FENCE_CMD_RES=$(bash -c "${FENCE_CMD}" | tee >(tail -n 1 > client_creds.txt))
                            file_content=$(cat client_creds.txt)

                            case "$CLIENT_TYPE" in
                                "implicit")
                                    CLIENT_CREDS=$(echo "$file_content" | sed -e "s/(\\('\\(.*\\)'\\),\\x27None\\27)/\\2,None/" -e "s/(\\('\\(.*\\)'\\), \\(.*\\))/\\2,\\3/")
                                    ;;
                                *)
                                    CLIENT_CREDS=$(echo "$file_content" | sed -e "s/(\\('\\(.*\\)'\\), '\\(.*\\)')/\\2,\\3/")
                            esac
                            json_output=$(jq -n --arg name "$CLIENT_NAME" --arg value "$CLIENT_CREDS" '{($name): $value}')
                            combined=$(jq --argjson new "$json_output" '. * $new' <<< "$combined")
                        done
                        echo "$combined" > clients_creds.json

                        # Run usersync
                        gen3 job run usersync -w ADD_DBGAP true

                        # Validate pods to roll up
                        gen3 kube-wait4-pods || true
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'create-fence-client/clients_creds.json'
        }
    }
}
