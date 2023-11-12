/*
    String parameter TARGET_ENVIRONMENT
        e.g., qa-anvil
    String parameter USERNAME
        Username
        e.g., cdis.autotest@gmail.com

    Artifact archived - api_key.json
*/
pipeline {
    agent {
        kubernetes {
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
    args: ["while [ $(curl -sw '%{http_code}' http://jenkins-master-service:8080/tcpSlaveAgentListener/ -o /dev/null) -ne 200 ]; do sleep 5; echo 'Waiting for jenkins connection ...'; done"]
  containers:
  - name: jnlp
    command: ["/bin/sh","-c"]
    args: ["sleep 30; /usr/local/bin/jenkins-agent"]
    resources:
      requests:
        cpu: 500m
        memory: 500Mi
        ephemeral-storage: 500Mi
  serviceAccount: jenkins-service
  serviceAccountName: jenkins-service
'''
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
                dir("generate-api-key") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${TARGET_ENVIRONMENT}
                            source $GEN3_HOME/gen3/gen3setup.sh
                            gen3 api api-key $USERNAME > api_key.json
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'generate-api-key/api_key.json'
        }
    }
}
