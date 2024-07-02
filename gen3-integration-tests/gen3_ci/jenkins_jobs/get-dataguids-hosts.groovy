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
        stage('Get Dataguids Hosts') {
            steps {
                dir("get-dataguids-host"){
                    script {
                        sh '''#!/bin/bash +x
                        set -e
                        export GEN3_HOME=\$WORKSPACE/cloud-automation
                        export KUBECTL_NAMESPACE=\${NAMESPACE}
                        source \$GEN3_HOME/gen3/gen3setup.sh

                        g3kubectl -n $KUBECTL_NAMESPACE get configmap manifest-all -o json | jq .data.json > dgmanifest.json
                        echo -e $(cat dgmanifest.json) | sed \‘s/\\//g\’ | sed \‘1s/^.//\’ | sed \‘$s/.$//\’ > dataguidmanifest.json
                        LIST=cat dataguidmanifest.json | jq -r \‘.indexd.dist[] | select(.type == “indexd”) | .host\’
                        echo "\$LIST" > hostlist.json
                        '''
                    }
                }
            }
        }
    }
     post {
        always {
            archiveArtifacts artifacts: 'get-dataguids-host/hostlist.json'
        }
    }
}
