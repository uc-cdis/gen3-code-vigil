/*
  String parameter NAMESPACE
    e.g., qa-anvil

  Archived artifacts - gitops.json, manifest.json
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
        stage('Fetch portal config') {
            steps {
                dir("fetch-portal-config") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source \$GEN3_HOME/gen3/gen3setup.sh
                            RESULT=`gen3 secrets decode portal-config gitops.json`
                            echo "\$RESULT" > gitops.json
                        '''
                    }
                }
            }
        }
        stage('Fetch manifest') {
            steps {
                dir("fetch-manifest") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source \$GEN3_HOME/gen3/gen3setup.sh
                            RESULT=`g3kubectl get configmaps manifest-global -o json`
                            echo "\$RESULT" > manifest.json
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'fetch-portal-config/gitops.json'
            archiveArtifacts artifacts: 'fetch-manifest/manifest.json'
        }
    }
}
