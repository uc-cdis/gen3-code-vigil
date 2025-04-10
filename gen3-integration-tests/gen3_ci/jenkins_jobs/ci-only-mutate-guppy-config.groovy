/*
    String parameter NAMESPACE
        e.g., qa-anvil
    String parameter INDEXNAME
        e.g., pfbexport, jenkins
    String parameter JENKINS_NAMESPACE
      Default value - default
    String parameter CLOUD_AUTO_BRANCH
        e.g., master

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
        stage('Update manifest.json') {
            steps {
                dir("cdis-manifest/${NAMESPACE}.planx-pla.net") {
                    script {
                        sh '''#!/bin/bash -x
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
        stage('Run Gen3 job') {
            steps {
                dir("ci-only-mutate-guppy-config") {
                    script {
                        sh '''#!/bin/bash -x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh
                            if [ "\${INDEXNAME}" == "jenkins" ]; then
                              echo "Executing commands for jenkins..."
                              g3kubectl -n \${NAMESPACE} get configmap manifest-guppy -o yaml > original_guppy_config.yaml
                              sed -i 's/"index": "[^"]*_subject"/"index": "'${INDEXNAME}_subject_alias'"/' original_guppy_config.yaml
                              sed -i '/"index": ".*_file"/ { /midrc/! s/"index": ".*_file"/"index": "'${INDEXNAME}_file_alias'"/ }' original_guppy_config.yaml
                              sed -i 's/"config_index": "[^"]*-config"/"config_index": "'${INDEXNAME}_configs_alias'"/' original_guppy_config.yaml
                            else
                              echo "Executing other commands..."
                              g3kubectl -n \${NAMESPACE} get configmap manifest-guppy -o yaml > original_guppy_config.yaml
                              etlMapping=$(kubectl -n \${NAMESPACE} get cm etl-mapping -o jsonpath='{.data.etlMapping\\.yaml}')
                              guppyConfig="$(yq '{indices:[.mappings[]|{index:.name,type:.doc_type}],auth_filter_field:"auth_resource_path"}' <<< "$etlMapping")"

                              subject_index=$(echo "$guppyConfig" | jq -r '.indices[] | select(.type == "subject") | .index')
                              file_index=$(echo "$guppyConfig" | jq -r '.indices[] | select(.type == "file") | .index')
                              sed -i 's/"index": "[^"]*_subject_alias"/"index": "'${subject_index}'"/' original_guppy_config.yaml
                              sed -i '/"index": ".*_file_alias"/ { /midrc/! s/"index": ".*_file_alias"/"index": "'${file_index}'"/ }' original_guppy_config.yaml
                            fi
                            cat original_guppy_config.yaml
                            g3kubectl -n \${NAMESPACE} delete configmap manifest-guppy
                            g3kubectl -n \${NAMESPACE} apply -f original_guppy_config.yaml
                            gen3 roll guppy
                            # Validate pods to roll up
                            gen3 kube-wait4-pods || true
                        '''
                    }
                }
            }
        }
    }
}
