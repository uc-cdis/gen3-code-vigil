/*
    String parameter CLIENT_NAME
        e.g. jenkinsClientTester

    Artifact archived -
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
                  branches: [[name: 'refs/heads/master']],
                  doGenerateSubmoduleConfigurations: false,
                  extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: 'cloud-automation']],
                  submoduleCfg: [],
                  userRemoteConfigs: [[credentialsId: 'PlanXCyborgUserJenkins', url: 'https://github.com/uc-cdis/cloud-automation.git']]
                ])
            }
        }
        stage('Delete Fence Client') {
            steps {
                dir("delete-fence-client"){
                    script {
                        sh '''#!/bin/bash +x
                        set -e
                        export GEN3_HOME=\$WORKSPACE/cloud-automation
                        export KUBECTL_NAMESPACE=\${NAMESPACE}
                        source $GEN3_HOME/gen3/gen3setup.sh

                        delete_fence_client="kubectl -n $KUBECTL_NAMESPACE exec $(gen3 pod fence) -- fence-create client-delete --client ${CLIENT_NAME}"
                        bash -c ${delete_fence_client}
                        if [ $? -eq 0 ]; then
                            echo "Command executed successfully."
                        else
                            echo "Command failed with an exit code $?."
                        fi
                        '''
                    }
                }
            }
        }
    }
}
