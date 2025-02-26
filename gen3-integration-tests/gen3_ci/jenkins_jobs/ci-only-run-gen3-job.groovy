/*
    String parameter NAMESPACE
        e.g., qa-anvil
    String parameter JOB_NAME
        e.g., metadata-aggregate-sync
    Boolean parameter GEN3_ROLL_ALL
        Default value - false
        e.g., true
    String parameter JENKINS_NAMESPACE
      Default value - default
    String parameter CLOUD_AUTO_BRANCH
        e.g., master
    String parameter SERVICE
        Key from the manifest's versions block
        e.g., metadata
    String parameter VERSION
        Version, specifically the quay image tag
        e.g., 2023.09

    Artifact archived - log.txt
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
        stage('Change service version') {
            steps {
                dir("cdis-manifest/${NAMESPACE}.planx-pla.net") {
                    script {
                        def service_value = params.SERVICE
                        if (service_value != 'None' && service_value.trim()) {
                          serviceList = SERVICE.split(',')
                          serviceList.each { SERVICE_NAME ->
                            currentBranch = "${SERVICE_NAME}:[a-zA-Z0-9._-]*"
                            targetBranch = "${SERVICE_NAME}:${VERSION}"
                            echo "Editing cdis-manifest/${NAMESPACE} service ${SERVICE_NAME} to version ${VERSION}"
                            sh 'sed -i -e "s,'+"${currentBranch},${targetBranch}"+',g" manifest.json'
                            sh 'cat manifest.json'
                          }
                        } else {
                            echo "Skipping as no value assigned for SERVICE..."
                        }
                    }
                }
            }
        }
        stage('Run Gen3 job') {
            steps {
                dir("ci-only-run-gen3-job") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh
                            if [ $GEN3_ROLL_ALL == "true" ]; then
                                gen3 roll all
                            fi
                            gen3 job run \${JOB_NAME}
                            kubectl -n ${KUBECTL_NAMESPACE} wait --for=condition=complete --timeout=-1s jobs/\${JOB_NAME}
                            gen3 job logs \${JOB_NAME} > log.txt
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'ci-only-run-gen3-job/log.txt'
        }
    }
}
