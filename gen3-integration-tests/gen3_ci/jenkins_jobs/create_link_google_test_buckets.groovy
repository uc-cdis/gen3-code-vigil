/*
    String parameter NAMESPACE
        e.g., qa-anvil
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
        stage('Create Link Google Test Buckets') {
            steps {
                dir("create-link-google-test-buckets"){
                    script {
                        sh '''#!/bin/bash +x
                        set -e
                        export GEN3_HOME=\$WORKSPACE/cloud-automation
                        export KUBECTL_NAMESPACE=\${NAMESPACE}
                        source $GEN3_HOME/gen3/gen3setup.sh

                        # Create Google Test Buckets
                        g3kubectl exec $(gen3 pod fence \${NAMESPACE}) -- fence-create google-bucket-create --unique-name dcf-integration-qa --google-project-id dcf-integration --project-auth-id QA --public False
                        g3kubectl exec $(gen3 pod fence \${NAMESPACE}) -- fence-create google-bucket-create --unique-name dcf-integration-test --google-project-id dcf-integration --project-auth-id test --public False

                        # Link phs ids to existing buckets
                        g3kubectl exec $(gen3 pod fence \${NAMESPACE}) -- fence-create link-bucket-to-project --project_auth_id phs000179 --bucket_id dcf-integration-qa --bucket_provider google
                        g3kubectl exec $(gen3 pod fence \${NAMESPACE}) -- fence-create link-bucket-to-project --project_auth_id phs000178 --bucket_id dcf-integration-test --bucket_provider google
                        '''
                    }
                }
            }
        }
    }
}
