/*
    String parameter NAMESPACE
        e.g., jenkins-brain
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
        stage('Unlock namespace') {
            steps {
                dir("unlock-namespace") {
                    script {
                        sh '''#!/bin/bash +x
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            source \$GEN3_HOME/gen3/gen3setup.sh
                            lockName=jenkins
                            echo "REPO: \$REPO"
                            echo "BRANCH: \$BRANCH"
                            branch=\$(echo "\$BRANCH" | sed \'s/[/()]/_/g\')
                            lockOwner="\$REPO-\$branch"
                            echo "lockOwner: \$lockOwner"
                            echo "attempting to unlock namespace \$NAMESPACE"
                            export KUBECTL_NAMESPACE="\$NAMESPACE"
                            klockResult=$(bash "\$GEN3_HOME/gen3/bin/klock.sh" "unlock" "\$lockName" "\$lockOwner")
                            if [[ $klockResult =~ ^.*labeled$ ]]; then
                                echo "Unlocked namespace \$KUBECTL_NAMESPACE"
                                exit 0
                            else
                                # Unable to unlock namespace
                                exit 1
                            fi
                        '''
                    }
                }
            }
        }
    }
}
