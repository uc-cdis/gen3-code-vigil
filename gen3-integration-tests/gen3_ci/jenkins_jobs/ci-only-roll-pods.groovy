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
            }
        }
        stage('Gen3 Roll') {
            steps {
                dir("ci-only-roll-pods") {
                    sh '''#!/bin/bash +x

                        set -e

                        export GEN3_HOME=\$WORKSPACE/cloud-automation
                        export KUBECTL_NAMESPACE=\${NAMESPACE}

                        source $GEN3_HOME/gen3/gen3setup.sh

                        gen3 gitops configmaps
                        gen3 roll \$SERVICE_NAME

                        gen3 kube-wait4-pods || true

                        echo "done"
                        exit 0
                    '''
                }
            }
        }
    }
}
