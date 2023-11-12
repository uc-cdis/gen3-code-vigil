/*
    String parameter TARGET_ENVIRONMENT
        e.g., qa-anvil
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
        stage('Roll the environment') {
            steps {
                dir("cdis-manifest/${TARGET_ENVIRONMENT}.planx-pla.net") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${TARGET_ENVIRONMENT}
                            source $GEN3_HOME/gen3/gen3setup.sh
                            yes | gen3 reset
                        '''
                    }
                }
            }
        }
        stage('Run usersync') {
            steps {
                dir("cdis-manifest/${TARGET_ENVIRONMENT}.planx-pla.net") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${TARGET_ENVIRONMENT}
                            source $GEN3_HOME/gen3/gen3setup.sh
                            gen3 job run usersync
                            g3kubectl wait --for=condition=complete --timeout=-1s jobs/usersync
                        '''
                    }
                }
            }
        }
    }
}
