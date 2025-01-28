/*
    String parameter NAMESPACE
        e.g. jenkins-blood

    String parameter CLOUD_AUTO_BRANCH
        e.g., refs/heads/master
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
                  branches: [[name: "${params.CLOUD_AUTO_BRANCH}"]],
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
                        source \$GEN3_HOME/gen3/gen3setup.sh


                        # CLIENT_NAME,USER_NAME,CLIENT_TYPE,ARBORIST_POLICIES,EXPIRES_IN
                        client_details=(
                            "basic-test-client"
                            "implicit-test-client"
                            "basic-test-abc-client"
                            "jenkins-client-tester"
                            "jenkins-client-no-expiration"
                            "jenkins-client-short-expiration"
                            "jenkins-client-medium-expiration"
                            "jenkins-client-long-expiration"
                            "ras-test-client"
                            "ras-test-client1"
                            "ras-test-client2"
                        )

                        combined='{}'
                        for CLIENT_NAME in "${client_details[@]}"; do
                            DELETE_CMD="kubectl -n $KUBECTL_NAMESPACE exec $(gen3 pod fence) -- fence-create client-delete --client ${CLIENT_NAME}"
                            echo "Running: ${DELETE_CMD}"
                            bash -c "${DELETE_CMD}"
                        done
                        '''
                    }
                }
            }
        }
    }
}
