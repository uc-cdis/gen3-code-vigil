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
                // data-simulator
                checkout([
                  $class: 'GitSCM',
                  branches: [[name: 'refs/heads/master']],
                  doGenerateSubmoduleConfigurations: false,
                  extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: 'data-simulator']],
                  submoduleCfg: [],
                  userRemoteConfigs: [[credentialsId: 'PlanXCyborgUser', url: 'https://github.com/uc-cdis/data-simulator.git']]
                ])
            }
        }
        stage('Run GenTestData') {
            steps {
                dir("run-gentestdata") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh

                            echo "Generating dummy data for the test ..."
                            gen3 job run gentestdata SUBMISSION_USER \${SUBMISSION_USER} MAX_EXAMPLES \${MAX_EXAMPLES} SUBMISSION_ORDER \${SUBMISSION_ORDER}
                            g3kubectl wait --for=condition=complete --timeout=-1s jobs/gentestdata
                        '''
                    }
                }
            }
        }
    }
}
