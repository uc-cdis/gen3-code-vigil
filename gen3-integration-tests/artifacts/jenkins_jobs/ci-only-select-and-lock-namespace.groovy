/*
    String parameter AVAILABLE_NAMESPACES
        Comma-separated list of available namespaces to run integration tests
        Default - ""
        e.g., jenkins-brain,jenkins-dcp,jenkins-genomel
    String parameter REPO
        e.g., gitops-qa
    String parameter BRANCH
        e.g. chore/update_portal_qabrh
*/
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
        stage('Select and lock namespace') {
            steps {
                dir("select-and-lock-namespace") {
                    script {
                        sh '''#!/bin/bash +x
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            source \$GEN3_HOME/gen3/gen3setup.sh
                            times=0
                            lockName=jenkins
                            echo "REPO: \$REPO"
                            echo "BRANCH: \$BRANCH"
                            branch=\$(echo "\$BRANCH" | sed \'s/[/()]/_/g\')
                            lockOwner="\$REPO-\$branch"
                            echo "lockOwner: \$lockOwner"
                            IFS=',' read -ra namespaces <<< "$AVAILABLE_NAMESPACES"
                            while [ "$times" -ne 120 ]; do
                                # Try to find an unlocked namespace
                                for ((i=0; i<\${#namespaces[@]}; i++)); do
                                    export KUBECTL_NAMESPACE="\${namespaces[$i]}"
                                    echo "attempting to lock namespace \$KUBECTL_NAMESPACE"
                                    klockResult=$(bash "$GEN3_HOME/gen3/bin/klock.sh" "lock" "\$lockName" "\$lockOwner" 10800 -w 60)
                                    echo "RESULT: \$klockResult"
                                    if [[ \$klockResult =~ ^.*labeled$ ]]; then
                                        echo "Selected namespace \$KUBECTL_NAMESPACE"
                                        echo "\$KUBECTL_NAMESPACE" > namespace.txt
                                        exit 0
                                    else
                                        # Unable to lock a namespace
                                        echo "no available workspace, yet..."
                                    fi
                                done
                                times=$((times + 1))
                                sleep 60
                            done
                        '''
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'select-and-lock-namespace/namespace.txt'
        }
    }
}
