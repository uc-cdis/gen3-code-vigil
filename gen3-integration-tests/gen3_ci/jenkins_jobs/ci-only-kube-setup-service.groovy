/*
  String parameter NAMESPACE
    e.g., qa-anvil

  String parameter SERVICENAME
    e.g., indexd, fence, etc

  String parameter CLOUD_AUTO_BRANCH
    e.g., master

  Archived artifacts -
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
        stage('Initial Setup') {
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
        stage('Kube Setup Service') {
            options {
                    timeout(time: 5, unit: 'MINUTES')   // timeout on this stage
                }
            steps {
                dir("ci-only-kube-setup-service"){
                    script {
                        try {
                            sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh

                            # Perform kube-setup-service
                            gen3 kube-setup-\${SERVICENAME}

                            # Validate pods to roll up
                            gen3 kube-wait4-pods || true
                            '''
                        }
                        catch (ex) {
                            metricsHelper.writeMetricWithResult(STAGE_NAME, false)
                            pipelineHelper.handleError(e)
                        }
                    }
                }
            }
        }
    }
}
