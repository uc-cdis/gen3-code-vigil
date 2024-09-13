/*
    String parameter JOB_NAME
    eg - manifest-indexing

    String parameter LABEL_NAME
    eg - sowerjob

    String parameter EXPECT_FAILURE (parameter for negative sceanrio)
    default value - False
    Note : This parameter is needed to be set to True if you want to test the negatve sceanrio
    where you are expecting the job pod to fail.
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
        stage('Check Kube Pod') {
            options {
                    timeout(time: 5, unit: 'MINUTES')   // timeout on this stage
                }
            steps {
                dir("ci-only-check-kube-pod"){
                    script {
                        try {
                            sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh

                            echo "NAMESPACE : $KUBECTL_NAMESPACE"
                            while true; do
                                sleep 10
                                echo "Waiting for $JOB_NAME job pod ..."

                                # checking if there are pods with LABEL_NAME mentioned in parameters
                                POD_NAMES=$(kubectl -n $KUBECTL_NAMESPACE get pod --sort-by=.metadata.creationTimestamp -l app=$LABEL_NAME -o json | jq -r '.items[] | select(.metadata.name | test("^'"$JOB_NAME"'")) | .metadata.name')
                                if [[ -z "$POD_NAMES" ]]; then
                                    echo "No pods found with label $LABEL_NAME"
                                else
                                    # if pod/s found, get the status of the latest pod
                                    LATEST_POD=$(echo "$POD_NAMES" | tail -n 1)
                                    echo "Pod found with label $LABEL_NAME: $LATEST_POD"
                                    POD_STATUS=$(kubectl -n $KUBECTL_NAMESPACE get pod $LATEST_POD -o jsonpath='{.status.phase}')
                                    echo "Pod status: $POD_STATUS"
                                    if [ "$POD_STATUS" == "Succeeded" ]; then
                                        echo "The container from pod $LATEST_POD is ready! Proceed with the assertion checks..."
                                        kubectl logs $LATEST_POD -n $NAMESPACE > logs.txt
                                        break
                                    elif [ "$POD_STATUS" == "Failed" ]; then
                                        if [ "$EXPECT_FAILURE" == "True" ]; then
                                            echo "The container from pod $LATEST_POD failed as expected! Just ignore as this is part of a negative test."
                                            kubectl logs $LATEST_POD -n $NAMESPACE > logs.txt
                                            break
                                        else
                                            echo "THE POD FAILED. GIVING UP."
                                            kubectl logs $LATEST_POD -n $NAMESPACE > logs.txt
                                            POD_LOGS=$(kubectl logs $LATEST_POD -n $NAMESPACE)
                                            echo "Logs:\n$POD_LOGS"
                                            exit 1
                                        fi
                                    fi
                                fi
                            done
                            '''
                        }
                        catch (ex) {
                            metricsHelper.writeMetricWithResult(STAGE_NAME, false)
                            pipelineHelper.handleError(e)
                        }
                    }
                }
            }
        }
    }
    post {
        always {
            archiveArtifacts artifacts: 'ci-only-check-kube-pod/logs.txt'
        }
    }
}
