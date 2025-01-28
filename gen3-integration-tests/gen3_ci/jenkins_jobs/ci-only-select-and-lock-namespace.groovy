/*
    String parameter AVAILABLE_NAMESPACES
        Comma-separated list of available namespaces to run integration tests
        Default - ""
        e.g., jenkins-brain,jenkins-dcp,jenkins-genomel
    String parameter REPO
        e.g., gitops-qa
    String parameter BRANCH
        e.g. chore/update_portal_qabrh
    String parameter JENKINS_NAMESPACE
      Default value - default
    String parameter CLOUD_AUTO_BRANCH
      e.g., master
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
                // cloud-automation
                checkout([
                  $class: 'GitSCM',
                  branches: [[name: "refs/heads/${CLOUD_AUTO_BRANCH}"]],
                  doGenerateSubmoduleConfigurations: false,
                  extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: 'cloud-automation']],
                  submoduleCfg: [],
                  userRemoteConfigs: [[credentialsId: 'PlanXCyborgUserJenkins', url: 'https://github.com/uc-cdis/cloud-automation.git']]
                ])
            }
        }
        stage('Select and lock namespace') {
            steps {
                dir("ci-only-select-and-lock-namespace") {
                    script {
                        sh '''#!/bin/bash +x
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            source \$GEN3_HOME/gen3/gen3setup.sh
                            times=0
                            lockName=jenkins
                            echo "REPO: \$REPO"
                            echo "BRANCH: \$BRANCH"
                            branch=\$(echo "\$BRANCH" | sed \'s/[/()]/_/g\')
                            lockOwner="\$REPO-\$branch"
                            echo "lockOwner: \$lockOwner"
                            IFS=',' read -ra namespaces <<< "$AVAILABLE_NAMESPACES"
                            while [ "$times" -ne 120 ]; do
                                # Try to find an unlocked namespace
                                for ((i=0; i<\${#namespaces[@]}; i++)); do
                                    export KUBECTL_NAMESPACE="\${namespaces[$i]}"
                                    echo "attempting to lock namespace \$KUBECTL_NAMESPACE"
                                    klockResult=$(bash "$GEN3_HOME/gen3/bin/klock.sh" "lock" "\$lockName" "\$lockOwner" 10800 -w 60)
                                    echo "RESULT: \$klockResult"
                                    if [[ \$klockResult =~ ^.*labeled$ ]]; then
                                        echo "Selected namespace \$KUBECTL_NAMESPACE"
                                        echo "\$KUBECTL_NAMESPACE" > namespace.txt
                                        exit 0
                                    else
                                        # Unable to lock a namespace
                                        echo "no available workspace, yet..."
                                    fi
                                done
                                times=$((times + 1))
                                sleep 60
                            done
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'ci-only-select-and-lock-namespace/namespace.txt'
        }
    }
}
