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
                        FENCE_CMD="kubectl exec $(gen3 pod fence) -- fence-create client-create"
                        echo "${FENCE_CMD}"

                        if [ -n "$ARBORIST_POLICIES" ] && [ -n "${ARBORIST_CLIENT_POLICIES}" ]; then
                            FENCE_CMD="${FENCE_CMD} --arborist http://arborist-service/ --policies ${ARBORIST_POLICIES}"
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

                        if [ -n "$EXPIRES_IN" ]; then
                            FENCE_CMD="${FENCE_CMD} --expires-in ${EXPIRES_IN}"
                        fi

                        echo "Running: ${FENCE_CMD}"
                        FENCE_CMD_RES=$(bash -c "${FENCE_CMD}")

                        client_id=$(echo "$FENCE_CMD_RES" | grep -oP "'([^']*)'" | head -n 1 | cut -c 2- | rev | cut -c 2- | rev)
                        client_secret=$(echo "$FENCE_CMD_RES" | grep -oP "'([^']*)'" | tail -n 1 | cut -c 2- | rev | cut -c 2- | rev)

                        # Extract client ID and secret (consider error handling and security)
                        CLIENT_ID=$(echo "$FENCE_CMD_RES" | grep -oP "'([^']*)'" | head -n 1 | cut -c 2- | rev | cut -c 2- | rev)
                        CLIENT_SECRET=$(echo "$FENCE_CMD_RES" | grep -oP "'([^']*)'" | tail -n 1 | cut -c 2- | rev | cut -c 2- | rev)

                        # Convert (ID, secret) to a list or custom JSON format (modify below)
                        client_data = ["${CLIENT_ID}", "${CLIENT_SECRET}"]  # Alternative: {"id": CLIENT_ID, "secret": CLIENT_SECRET}

                        # Store data in JSON file
                        echo "Storing client data in client_data.json..."
                        with open('client_data.json', 'w') as json_file:
                            json.dump(client_data, json_file, indent=4)

                        echo "Client data stored!"
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'create-fence-client/client_creds.json'
        }
    }
}
