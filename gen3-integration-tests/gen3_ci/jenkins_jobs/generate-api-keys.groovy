/*
    This Jenkins job will help generate api keys for test users on given Target environment

    String parameter NAMESPACE
        e.g., qa-anvil

    String parameter CLOUD_AUTO_BRANCH
        e.g., master

    Artifact archived - {NAMESPACE}_main_account.json, {NAMESPACE}_indexing_account.json
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
                            deploymentImages=$(kubectl -n \${NAMESPACE} get cm manifest-all -o jsonpath='{.data.json}' | jq '.versions')
                            echo "\${deploymentImages}" | jq --argjson newVersions "\$deploymentImages" '.versions = $newVersions' manifest.json > tmp_manifest.json && mv tmp_manifest.json manifest.json
                            cat manifest.json
                        '''
                    }
                }
            }
        }
        stage('Generate API Key') {
            steps {
                dir("generate-api-key") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh
                            echo "creating main_account api key for \$NAMESPACE"
                            gen3 api api-key main@example.org > \${NAMESPACE}_main_account.json

                            echo "creating indexing_account for \$NAMESPACE"
                            gen3 api api-key indexing@example.org > \${NAMESPACE}_indexing_account.json

                            echo "creating auxAcct1 for \$NAMESPACE"
                            gen3 api api-key dummy-one@example.org > \${NAMESPACE}_dummy_one.json

                            echo "creating auxAcct2 for \$NAMESPACE"
                            gen3 api api-key smarty-two@example.org > \${NAMESPACE}_smarty_two.json

                            echo "creating user0 for \$NAMESPACE"
                            gen3 api api-key user0@example.org > \${NAMESPACE}_user0_account.json

                            echo "creating user1 for \$NAMESPACE"
                            gen3 api api-key user1@example.org > \${NAMESPACE}_user1_account.json

                            echo "creating user2 for \$NAMESPACE"
                            gen3 api api-key user2@example.org > \${NAMESPACE}_user2_account.json
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'generate-api-key/*.json'
        }
    }
}
