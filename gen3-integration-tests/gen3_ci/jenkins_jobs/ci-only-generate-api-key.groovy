/*
    String parameter NAMESPACE
        e.g., qa-anvil
    String parameter USERNAME
        Username
        e.g., cdis.autotest@gmail.com
    String parameter JENKINS_NAMESPACE
    Default value - default

    Artifact archived - api_key.json
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
        memory: 1Gi
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
        stage('Generate API Key') {
            steps {
                dir("ci-only-generate-api-key") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh

                            echo "creating main_account api key for \$NAMESPACE"
                            gen3 api api-key cdis.autotest@gmail.com > \${NAMESPACE}_main_account.json

                            echo "creating indexing_account for \$NAMESPACE"
                            gen3 api api-key ctds.indexing.test@gmail.com > \${NAMESPACE}_indexing_account.json

                            echo "creating auxAcct1 for \$NAMESPACE"
                            gen3 api api-key dummy-one@planx-pla.net > \${NAMESPACE}_auxAcct1_account.json

                            echo "creating auxAcct2 for \$NAMESPACE"
                            gen3 api api-key smarty-two@planx-pla.net > \${NAMESPACE}_auxAcct2_account.json

                            echo "creating user0 for \$NAMESPACE"
                            gen3 api api-key dcf-integration-test-0@planx-pla.net > \${NAMESPACE}_user0_account.json

                            echo "creating user1 for \$NAMESPACE"
                            gen3 api api-key dcf-integration-test-1@planx-pla.net > \${NAMESPACE}_user1_account.json

                            echo "creating user2 for \$NAMESPACE"
                            gen3 api api-key dcf-integration-test-2@planx-pla.net > \${NAMESPACE}_user2_account.json
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'ci-only-generate-api-key/*.json'
        }
    }
}
