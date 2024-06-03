/*
    String parameter JOBNAME
    eg - manifest-indexing

    String parameter LABELNAME
    eg - sowerjob

    String parameter EXPECTFAILURE
    default value - False
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
                dir("check-kube-pod"){
                    script {
                        try {
                            sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh

                            N_ATTEMPTS=10
                            echo "NAMESPACE : $KUBECTL_NAMESPACE"
                            for (( i=1; i<=N_ATTEMPTS; i++ )); do
                                sleep 10
                                echo "Waiting for $JOBNAME job pod ..."

                                # checking if there are pods with labelname mentioned in parameters
                                podNames=$(g3kubectl -n $KUBECTL_NAMESPACE get pod --sort-by=.metadata.creationTimestamp -l app=$LABELNAME -o jsonpath="{.items[*].metadata.name}")
                                if [[ -z "$podNames" ]]; then
                                    echo "No pods found with label $LABELNAME"
                                else
                                    # if pod/s found, get the status of the latest pod
                                    latestPodName=$(echo "$podNames" | awk '{print $NF}')
                                    echo "Pod found with label $LABELNAME: $latestPodName"
                                    podStatus=$(g3kubectl -n $KUBECTL_NAMESPACE get pod $latestPodName -o jsonpath='{.status.phase}')

                                    if [ "$podStatus" == "Succeeded" ]; then
                                        echo "The container from pod $latestPodName is ready! Proceed with the assertion checks..."
                                        break
                                    elif [ "$podStatus" == "Failed" ]; then
                                        if [ "$EXPECTFAILURE" == "True" ]; then
                                            echo "The container from pod $latestPodName failed as expected! Just ignore as this is part of a negative test."
                                            break
                                        else
                                            echo "THE POD FAILED ON ATTEMPT $i. GIVING UP."
                                            pod_logs=$(kubectl logs $latestPodName -n $NAMESPACE)
                                            echo "Logs:\n$pod_logs"
                                            exit 1
                                        fi
                                    fi
                                fi
                                if [ $i -eq $N_ATTEMPTS ]; then
                                    echo "Max number of attempts reached: $i. Test has failed."
                                    exit 1
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
}
