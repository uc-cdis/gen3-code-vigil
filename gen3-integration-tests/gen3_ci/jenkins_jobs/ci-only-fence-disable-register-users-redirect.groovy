/*
    String parameter NAMESPACE
        e.g., qa-anvil
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
        stage('Fence Disable Register Users Redirect') {
            steps {
                dir("fence-disable-user-register-redirect") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source \$GEN3_HOME/gen3/gen3setup.sh

                            # Dump the current secret in a temp file.
                            gen3 secrets decode fence-config > fence_config_tmp.yaml; sed -i \'1d;$d\' fence_config_tmp.yaml

                            # Add the config we need at the bottom of the file
                            sed -i \'/REGISTER_USERS_ON/d\' fence_config_tmp.yaml; sed -i \'/REGISTERED_USERS_GROUP/d\' fence_config_tmp.yaml

                            # Update the secret
                            kubectl get secret fence-config -o json | jq --arg new_config "$(cat fence_config_tmp.yaml | base64)" \'.data["fence-config.yaml"]=$new_config\' | kubectl apply -f -

                            # Roll Fence
                            rm fence_config_tmp.yaml; gen3 roll fence; gen3 kube-setup-portal

                            # Validate pods to roll up
                            gen3 kube-wait4-pods || true
                        '''
                    }
                }
            }
        }
    }
}
