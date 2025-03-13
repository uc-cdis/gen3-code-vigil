/*
  String parameter NAMESPACE
    e.g., qa-anvil

  String parameter SERVICE
    e.g., sheepdog, indexd

  String parameter EXPIRATION
    e.g., 1, 300 (value in seconds)

  String parameter USERNAME
    e.g., main@example.org
  This is to help create access token

  String parameter CLOUD_AUTO_BRANCH
    e.g., master

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
                            deploymentImages=$(kubectl -n \${NAMESPACE} get deployments -o=jsonpath='{range .items[*]}"{.metadata.name}":"{.spec.template.spec.containers[*].image}",{"\\n"}{end}' | sed 's/-deployment//')
                            # Remove last trailing comma
                            deploymentImages="\${deploymentImages%?}"
                            formattedImages="{ \${deploymentImages} }"
                            echo "\${formattedImages}" | jq --argjson newVersions "\$formattedImages" '.versions = $newVersions' manifest.json > tmp_manifest.json && mv tmp_manifest.json manifest.json
                            cat manifest.json
                        '''
                    }
                }
            }
        }
        stage('Create Access Token') {
            options {
                    timeout(time: 5, unit: 'MINUTES')   // timeout on this stage
                }
            steps {
                dir("create-access-token") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh

                            # Create access token
                            kubectl exec -n ${KUBECTL_NAMESPACE} $(gen3 pod \$SERVICE \$NAMESPACE) -- fence-create token-create --scopes openid,user,fence,data,credentials,google_service_account,google_credentials --type access_token --exp \$EXPIRATION --username \$USERNAME > access_token.txt
                            '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'create-access-token/access_token.txt'
        }
    }
}
