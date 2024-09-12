/*
  String parameter NAMESPACE
    e.g., qa-anvil

  String parameter AUDIT_LOGGING
    e.g., true - Enabled the audit logging onto the target environment
          false - Disables the audit logging onto the target environment

  Archived artifacts -
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
        stage('Audit Service Logging') {
            options {
                    timeout(time: 5, unit: 'MINUTES')   // timeout on this stage
                }
            steps {
                dir("ci-only-audit-service-logging"){
                    script {
                        try {
                            sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh

                            # Dumping the current secret in a temp file
                            gen3 secrets decode fence-config > fence_config_tmp.yaml; sed -i '1d;$d' fence_config_tmp.yaml

                            # Add entry into fence_config_tmp.yaml to enable audit service logging
                            shopt -s xpg_echo; echo "ENABLE_AUDIT_LOGS:\n  presigned_url: \${AUDIT_LOGGING}\n  login: \${AUDIT_LOGGING}" >> fence_config_tmp.yaml

                            # Update the Secret
                            kubectl get secret fence-config -o json -n ${KUBECTL_NAMESPACE} | jq --arg new_config "$(cat fence_config_tmp.yaml | base64)" '.data["fence-config.yaml"]=$new_config' | kubectl -n ${KUBECTL_NAMESPACE} apply -f -

                            # Roll the fence and presigned-url-fence pods
                            gen3 roll fence; gen3 roll presigned-url-fence

                            # Validate pods to roll up
                            gen3 kube-wait4-pods || true
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
