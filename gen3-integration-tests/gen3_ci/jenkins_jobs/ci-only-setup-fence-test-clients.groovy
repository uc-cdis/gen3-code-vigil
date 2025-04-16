/*
    String parameter NAMESPACE
        e.g. jenkins-blood

    String parameter CLIENTS_DATA

    String parameter CLOUD_AUTO_BRANCH
        e.g., master

    Artifact archived - clients_creds.txt
                      - client_rotate_creds.txt
*/
pipeline {
    agent {
        kubernetes {
            namespace "${JENKINS_NAMESPACE}"
            yaml '''
apiVersion: v1
kind: Pod
metadata:
  annotations:
    karpenter.sh/do-not-evict: true
  labels:
    app: ephemeral-ci-run
    netnolimit: "yes"
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: eks.amazonaws.com/capacityType
            operator: In
            values:
            - ONDEMAND
        - matchExpressions:
          - key: karpenter.sh/capacity-type
            operator: In
            values:
            - on-demand
  initContainers:
  - name: wait-for-jenkins-connection
    image: quay.io/cdis/gen3-ci-worker:master
    command: ["/bin/sh","-c"]
    args: ["while [ $(curl -sw '%{http_code}' http://jenkins-master-service:8080/tcpSlaveAgentListener/ -o /dev/null) -ne 200 ]; do sleep 5; echo 'Waiting for jenkins connection...'; done"]
  containers:
  - name: jnlp
    command: ["/bin/sh","-c"]
    args: ["sleep 30; /usr/local/bin/jenkins-agent"]
    resources:
      requests:
        cpu: 500m
        memory: 500Mi
        ephemeral-storage: 1Gi
  - name: shell
    image: quay.io/cdis/gen3-ci-worker:master
    imagePullPolicy: Always
    command:
    - sleep
    args:
    - infinity
    resources:
      requests:
        cpu: 500m
        memory: 500Mi
        ephemeral-storage: 1Gi
    env:
    - name: AWS_DEFAULT_REGION
      value: us-east-1
    - name: JAVA_OPTS
      value: "-Xmx3072m"
    - name: AWS_ACCESS_KEY_ID
      valueFrom:
        secretKeyRef:
          name: jenkins-secret
          key: aws_access_key_id
    - name: AWS_SECRET_ACCESS_KEY
      valueFrom:
        secretKeyRef:
          name: jenkins-secret
          key: aws_secret_access_key
  serviceAccount: jenkins-service
  serviceAccountName: jenkins-service
'''
            defaultContainer 'shell'
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
                script {
                    sh '''#!/bin/bash +x
                        set -e
                        echo NAMESPACE: $NAMESPACE
                    '''
                }
                // cloud-automation
                checkout([
                  $class: 'GitSCM',
                  branches: [[name: "refs/heads/${params.CLOUD_AUTO_BRANCH}"]],
                  doGenerateSubmoduleConfigurations: false,
                  extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: 'cloud-automation']],
                  submoduleCfg: [],
                  userRemoteConfigs: [[credentialsId: 'PlanXCyborgUserJenkins', url: 'https://github.com/uc-cdis/cloud-automation.git']]
                ])
                // gitops-qa
                checkout([
                  $class: 'GitSCM',
                  branches: [[name: 'refs/heads/master']],
                  doGenerateSubmoduleConfigurations: false,
                  extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: 'cdis-manifest']],
                  submoduleCfg: [],
                  userRemoteConfigs: [[credentialsId: 'PlanXCyborgUserJenkins', url: 'https://github.com/uc-cdis/gitops-qa.git']]
                ])
            }
        }
        stage('Update manifest.json') {
            steps {
                dir("cdis-manifest/${NAMESPACE}.planx-pla.net") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh
                            deploymentImages=$(kubectl -n \${NAMESPACE} get cm manifest-all -o jsonpath='{.data.json}' | jq '.versions')
                            echo "\${deploymentImages}" | jq --argjson newVersions "\$deploymentImages" '.versions = $newVersions' manifest.json > tmp_manifest.json && mv tmp_manifest.json manifest.json
                            cat manifest.json
                        '''
                    }
                }
            }
        }
        stage('Create Setup Fence Test Clients') {
            options {
                    timeout(time: 20, unit: 'MINUTES')   // timeout on this stage
                }
            steps {
                dir("ci-only-setup-fence-test-clients"){
                    script {
                        sh '''#!/bin/bash +x
                        set -e
                        export GEN3_HOME=\$WORKSPACE/cloud-automation
                        export KUBECTL_NAMESPACE=\${NAMESPACE}
                        source $GEN3_HOME/gen3/gen3setup.sh

                        # Remove the first line which contains headers
                        CLIENTS_DATA=$(echo "$CLIENTS_DATA" | tail -n +2)

                        while IFS= read -r line; do
                            # Split the variable into an array using comma as the delimiter
                            IFS=',' read -r CLIENT_NAME USER_NAME CLIENT_TYPE ARBORIST_POLICIES EXPIRES_IN SCOPES<<< "${line}"
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
                        done <<< "$CLIENTS_DATA"


                        # PERFORMING CLIENT ROTATION
                        # CLIENT_NAME,EXPIRES_IN
                        client_details=(
                            "jenkins-client-tester,"
                        )

                        for value in "${client_details[@]}"; do
                            # Split the variable into an array using comma as the delimiter
                            IFS=',' read -r CLIENT_NAME EXPIRES_IN <<< "${value}"
                            # construct fence-create command depending on the parameters provided by the run
                            FENCE_CMD="kubectl -n $KUBECTL_NAMESPACE exec $(gen3 pod fence) -- fence-create client-rotate --client ${CLIENT_NAME}"
                            echo "${FENCE_CMD}"
                            if [[ -n $EXPIRES_IN ]]; then
                                FENCE_CMD="${FENCE_CMD} --expires-in ${EXPIRES_IN}"
                            fi
                            echo "Running: ${FENCE_CMD}"
                            # execute the above fence command
                            FENCE_CMD_RES=$(bash -c "${FENCE_CMD}" | tee >(awk -v prefix="$CLIENT_NAME" 'END{print prefix ":" $0}' >> client_rotate_creds.txt))
                        done
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'ci-only-setup-fence-test-clients/*.txt'
        }
    }
}
