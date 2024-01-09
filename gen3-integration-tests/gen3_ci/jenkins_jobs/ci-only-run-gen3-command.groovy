/*
    String parameter NAMESPACE
        e.g., qa-anvil
    String parameter COMMAND
        e.g., gen3 secrets decode portal-config gitops.json | jq '.discoveryConfig.minimalFieldMapping.uid'

    Artifact archived - result.txt
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
        stage('Run command on adminvm') {
            steps {
                dir("run-command") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source \$GEN3_HOME/gen3/gen3setup.sh
                            RESULT=`\$COMMAND`
                            echo "\$RESULT" > result.txt
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'run-command/result.txt'
        }
    }
}
