/*
    String parameter NAMESPACE
        e.g., qa-anvil
    String parameter JENKINS_NAMESPACE
      Default value - default
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
                // cdis-manifest
                checkout([
                  $class: 'GitSCM',
                  branches: [[name: 'refs/heads/master']],
                  doGenerateSubmoduleConfigurations: false,
                  extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: 'temp-cdis-manifest']],
                  submoduleCfg: [],
                  userRemoteConfigs: [[credentialsId: 'PlanXCyborgUserJenkins', url: 'https://github.com/uc-cdis/cdis-manifest.git']]
                ])
            }
        }
        stage('Change service version') {
            steps {
                dir("cdis-manifest/${NAMESPACE}.planx-pla.net") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh
                            export TEMP_MANIFEST_HOME=\$WORKSPACE/temp-cdis-manifest
                            export MANIFEST_HOME=\$WORKSPACE/cdis-manifest
                            # UPDATE Versions Block
                            versions=$(jq '.versions' \$TEMP_MANIFEST_HOME/healdata.org/manifest.json)
                            jq --argjson versions "$versions" '.versions = $versions' manifest.json > versions_updated.json && mv versions_updated.json manifest.json
                            rm -rf versions_updated.json

                            # UPDATE Netpolicy in Global block
                            netpolicy=$(jq -r '.global.netpolicy // empty' \$TEMP_MANIFEST_HOME/healdata.org/manifest.json)
                            if [[ -n "$netpolicy" ]]; then
                                jq --arg netpolicy "$netpolicy" \
                                '.global.netpolicy = $netpolicy' manifest.json > netpolicy_updated.json && mv netpolicy_updated.json manifest.json
                                rm -rf netpolicy_updated.json
                                echo "Updated netpolicy"
                            fi

                            # UPDATE Frontend Root in Global block
                            frontend_root=$(jq -r '.global.frontend_root // empty' \$TEMP_MANIFEST_HOME/healdata.org/manifest.json)
                            if [[ -n "$frontend_root" ]]; then
                                jq --arg frontend_root "$frontend_root" \
                                '.global.frontend_root = $frontend_root' manifest.json > frontend_root_updated.json && mv frontend_root_updated.json manifest.json
                                rm -rf frontend_root_updated.json
                                echo "Updated frontend_root"
                            fi

                            # UPDATE ES7 in Global block
                            es7=$(jq -r '.global.es7 // empty' \$TEMP_MANIFEST_HOME/healdata.org/manifest.json)
                            if [[ -n "$es7" ]]; then
                                jq --arg es7 "$es7" \
                                '.global.es7 = $es7' manifest.json > es7_updated.json && mv es7_updated.json manifest.json
                                rm -rf es7_updated.json
                                echo "Updated es7"
                            fi

                            # Update Manifest Block
                            block_names=("portal" "ssjdispatcher" "indexd" "metadata" "mariner" "awsstoragegateway" "sower")
                            for block_name in "${block_names[@]}"; do
                                block=$(jq -r ".${block_name} // empty" "${TEMP_MANIFEST_HOME}/healdata.org/manifest.json")
                                if [[ -n "$block" ]]; then
                                    echo "Updating ${block_name} block in manifest.json..."  # Correctly expand the variable
                                    jq --argjson block "$block" ".${block_name} = \$block" manifest.json > "${block_name}_updated.json" && mv "${block_name}_updated.json" manifest.json
                                    rm -rf ${block_name}_updated.json
                                fi
                            done


                            # Update Sower block
                            # PRINT the manifest.json at the end
                            jq . manifest.json


                        '''
                    }
                }
            }
        }
    }
}
