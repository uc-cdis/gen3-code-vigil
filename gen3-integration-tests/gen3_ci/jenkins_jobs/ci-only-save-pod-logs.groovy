/*
    String parameter NAMESPACE
        e.g., qa-anvil
    Artifacts archived - zipped pod logs
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
        stage('Save pod logs') {
            steps {
                dir("save-pod-logs") {
                    script {
                        sh '''#!/bin/bash +x
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\$NAMESPACE
                            source \$GEN3_HOME/gen3/gen3setup.sh
                            gen3 logs snapshot
                            echo "\$RESULT" > result.txt
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'save-pod-logs/*.log.gz'
        }
    }
}
