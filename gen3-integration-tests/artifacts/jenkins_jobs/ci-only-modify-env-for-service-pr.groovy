/*
    String parameter TARGET_ENVIRONMENT
        e.g., qa-anvil
    String parameter SERVICE
        Key from the manifest's versions block
        e.g., metadata
    String parameter VERSION
        Version, specifically the quay image tag
        e.g., 2023.09
*/
pipeline {
    agent {
      node {
        label 'gen3-qa-worker'
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
        stage('Change service version and roll env') {
            steps {
                dir("cdis-manifest/${TARGET_ENVIRONMENT}.planx-pla.net") {
                    script {
                        currentBranch = "${SERVICE}:[a-zA-Z0-9._-]*"
                        targetBranch = "${SERVICE}:${VERSION}"
                        echo "Editing cdis-manifest/${TARGET_ENVIRONMENT} service ${SERVICE} to version ${VERSION}"
                        sh 'sed -i -e "s,'+"${currentBranch},${targetBranch}"+',g" manifest.json'
                        sh 'cat manifest.json'
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${TARGET_ENVIRONMENT}
                            source $GEN3_HOME/gen3/gen3setup.sh
                            yes | gen3 reset
                            gen3 job run usersync
                            g3kubectl wait --for=condition=complete --timeout=-1s jobs/usersync
                        '''
                    }
                }
            }
        }
    }
}
