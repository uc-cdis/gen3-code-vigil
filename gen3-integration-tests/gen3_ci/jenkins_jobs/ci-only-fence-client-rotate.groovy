/*
    String parameter NAMESPACE
        e.g. jenkins-blood
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
        stage('Fence Client Rotation') {
            steps {
                dir("ci-only-fence-client-rotate"){
                    script {
                        sh '''#!/bin/bash +x
                        set -e
                        export GEN3_HOME=\$WORKSPACE/cloud-automation
                        export KUBECTL_NAMESPACE=\${NAMESPACE}
                        source $GEN3_HOME/gen3/gen3setup.sh
                        # CLIENT_NAME,EXPIRES_IN
                        client_details=(
                            "jenkins-client-tester,"
                        )

                        for value in "${client_details[@]}"; do
                            # Split the variable into an array using comma as the delimiter
                            IFS=',' read -r CLIENT_NAME EXPIRES_IN <<< "${value}"
                            # construct fence-create command depending on the parameters provided by the run
                            FENCE_CMD="kubectl -n $KUBECTL_NAMESPACE exec $(gen3 pod fence) -- fence-create client-rotate --client ${CLIENT_NAME}"
                            echo "${FENCE_CMD}"
                            if [[ -n $EXPIRES_IN ]]; then
                                FENCE_CMD="${FENCE_CMD} --expires-in ${EXPIRES_IN}"
                            fi
                            echo "Running: ${FENCE_CMD}"
                            # execute the above fence command
                            FENCE_CMD_RES=$(bash -c "${FENCE_CMD}" | tee >(awk -v prefix="$CLIENT_NAME" 'END{print prefix ":" $0}' >> client_rotate_creds.txt))
                        done

                        # Run usersync
                        gen3 job run usersync ADD_DBGAP true
                        kubectl wait --for=condition=complete --timeout=-1s jobs/usersync
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'ci-only-fence-client-rotate/client_rotate_creds.txt'
        }
    }
}
