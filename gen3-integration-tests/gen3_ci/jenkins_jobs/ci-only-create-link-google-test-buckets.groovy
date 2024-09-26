/*
    String parameter NAMESPACE
        e.g., qa-anvil
    String parameter JENKINS_NAMESPACE
      Default value - default
    Artifact archived - None
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
        stage('Create Link Google Test Buckets') {
            steps {
                dir("ci-only-create-link-google-test-buckets"){
                    script {
                        sh '''#!/bin/bash +x
                        set -e
                        export GEN3_HOME=\$WORKSPACE/cloud-automation
                        export KUBECTL_NAMESPACE=\${NAMESPACE}
                        source $GEN3_HOME/gen3/gen3setup.sh

                        # Create Google Test Buckets
                        kubectl exec -n ${KUBECTL_NAMESPACE} $(gen3 pod fence \${NAMESPACE}) -- fence-create google-bucket-create --unique-name dcf-integration-qa --google-project-id dcf-integration --project-auth-id QA --public False
                        kubectl exec -n ${KUBECTL_NAMESPACE} $(gen3 pod fence \${NAMESPACE}) -- fence-create google-bucket-create --unique-name dcf-integration-test --google-project-id dcf-integration --project-auth-id test --public False

                        # Link phs ids to existing buckets
                        kubectl exec -n ${KUBECTL_NAMESPACE} $(gen3 pod fence \${NAMESPACE}) -- fence-create link-bucket-to-project --project_auth_id phs000179 --bucket_id dcf-integration-qa --bucket_provider google
                        kubectl exec -n ${KUBECTL_NAMESPACE} $(gen3 pod fence \${NAMESPACE}) -- fence-create link-bucket-to-project --project_auth_id phs000178 --bucket_id dcf-integration-test --bucket_provider google
                        '''
                    }
                }
            }
        }
    }
}
