/*
    String parameter NAMESPACE
        e.g., qa-anvil
    String parameter JENKINS_NAMESPACE
      Default value - default
    String parameter CLOUD_AUTO_BRANCH
      e.g., master
    String parameter UPDATED_FOLDER
      Folder in repository that was updated
    String parameter TARGET_REPO
      Repository from where files will be pulled
*/
pipeline {
    agent {
        kubernetes {
            namespace "${JENKINS_NAMESPACE}"
            yaml '''
apiVersion: v1
kind: Pod
metadata:
  annotations:
    karpenter.sh/do-not-evict: true
  labels:
    app: ephemeral-ci-run
    netnolimit: "yes"
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: eks.amazonaws.com/capacityType
            operator: In
            values:
            - ONDEMAND
        - matchExpressions:
          - key: karpenter.sh/capacity-type
            operator: In
            values:
            - on-demand
  initContainers:
  - name: wait-for-jenkins-connection
    image: quay.io/cdis/gen3-ci-worker:master
    command: ["/bin/sh","-c"]
    args: ["while [ $(curl -sw '%{http_code}' http://jenkins-master-service:8080/tcpSlaveAgentListener/ -o /dev/null) -ne 200 ]; do sleep 5; echo 'Waiting for jenkins connection...'; done"]
  containers:
  - name: jnlp
    command: ["/bin/sh","-c"]
    args: ["sleep 30; /usr/local/bin/jenkins-agent"]
    resources:
      requests:
        cpu: 500m
        memory: 500Mi
        ephemeral-storage: 1Gi
  - name: shell
    image: quay.io/cdis/gen3-ci-worker:master
    imagePullPolicy: Always
    command:
    - sleep
    args:
    - infinity
    resources:
      requests:
        cpu: 500m
        memory: 500Mi
        ephemeral-storage: 1Gi
    env:
    - name: AWS_DEFAULT_REGION
      value: us-east-1
    - name: JAVA_OPTS
      value: "-Xmx3072m"
    - name: AWS_ACCESS_KEY_ID
      valueFrom:
        secretKeyRef:
          name: jenkins-secret
          key: aws_access_key_id
    - name: AWS_SECRET_ACCESS_KEY
      valueFrom:
        secretKeyRef:
          name: jenkins-secret
          key: aws_secret_access_key
  serviceAccount: jenkins-service
  serviceAccountName: jenkins-service
'''
            defaultContainer 'shell'
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
                script {
                    sh '''#!/bin/bash +x
                        set -e
                        echo NAMESPACE: $NAMESPACE
                    '''
                }
                // cloud-automation
                checkout([
                  $class: 'GitSCM',
                  branches: [[name: "refs/heads/${params.CLOUD_AUTO_BRANCH}"]],
                  doGenerateSubmoduleConfigurations: false,
                  extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: 'cloud-automation']],
                  submoduleCfg: [],
                  userRemoteConfigs: [[credentialsId: 'PlanXCyborgUserJenkins', url: 'https://github.com/uc-cdis/cloud-automation.git']]
                ])
                // gitops-qa
                checkout([
                  $class: 'GitSCM',
                  branches: [[name: 'refs/heads/master']],
                  doGenerateSubmoduleConfigurations: false,
                  extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: 'cdis-manifest']],
                  submoduleCfg: [],
                  userRemoteConfigs: [[credentialsId: 'PlanXCyborgUserJenkins', url: 'https://github.com/uc-cdis/gitops-qa.git']]
                ])
                // gitops-qa/cdis-manifest
                checkout([
                  $class: 'GitSCM',
                  branches: [[name: 'refs/heads/master']],
                  doGenerateSubmoduleConfigurations: false,
                  extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: 'temp-cdis-manifest']],
                  submoduleCfg: [],
                  userRemoteConfigs: [[credentialsId: 'PlanXCyborgUserJenkins', url: "https://github.com/uc-cdis/${params.TARGET_REPO}.git"]]
                ])
            }
        }
        stage('Set Env Variables') {
            steps {
                script {
                  env.GEN3_HOME = "${WORKSPACE}/cloud-automation"
                  env.KUBECTL_NAMESPACE = "${NAMESPACE}"
                  env.TEMP_MANIFEST_HOME= "${WORKSPACE}/temp-cdis-manifest/${UPDATED_FOLDER}"
                  env.MANIFEST_HOME= "${WORKSPACE}/cdis-manifest"
                }
            }
        }
        stage('Merge Manifest') {
            steps {
                dir("${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net") {
                    script {
                        String od = sh(returnStdout: true, script: "jq -r .global.dictionary_url < ${env.TEMP_MANIFEST_HOME}/manifest.json").trim()
                        String pa = sh(returnStdout: true, script: "jq -r .global.portal_app < ${env.TEMP_MANIFEST_HOME}/manifest.json").trim()
                        // fetch netpolicy from the target environment
                        sh(returnStatus : true, script: "if cat ${env.TEMP_MANIFEST_HOME}/manifest.json | jq --exit-status '.global.netpolicy' >/dev/null; then "
                          + "jq -r .global.netpolicy < ${env.TEMP_MANIFEST_HOME}/manifest.json > netpolicy.json; "
                          + "fi")
                        // fetch sower block from the target environment
                        sh "jq -r .sower < ${env.TEMP_MANIFEST_HOME}/manifest.json > sower_block.json"
                        // copy frontend_root if present
                        sh(returnStatus : true, script: "if cat ${env.TEMP_MANIFEST_HOME}/manifest.json | jq --exit-status '.global.frontend_root' >/dev/null; then "
                          + "jq -r .global.frontend_root < ${env.TEMP_MANIFEST_HOME}/manifest.json > frontend_root.json; "
                          + "fi")
                        // copy es7 if present
                        sh(returnStatus : true, script: "if cat ${env.TEMP_MANIFEST_HOME}/manifest.json | jq --exit-status '.global.es7' >/dev/null; then "
                          + "jq -r .global.es7 < ${env.TEMP_MANIFEST_HOME}/manifest.json > es7.json; "
                          + "fi")
                        def manifestBlockKeys = ["portal", "ssjdispatcher", "indexd", "metadata", "mariner", "awsstoragegateway"]
                        for (String item : manifestBlockKeys) {
                          sh(returnStdout: true, script: "if cat ${env.TEMP_MANIFEST_HOME}/manifest.json | jq --exit-status '.${item}' >/dev/null; then "
                            + "jq -r .${item} < ${env.TEMP_MANIFEST_HOME}/manifest.json > ${item}_block.json; "
                            + "fi")
                        }

                        String s = sh(returnStdout: true, script: "jq -r keys < ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json")
                        println s
                        def keys = new groovy.json.JsonSlurper().parseText(s)
                        String dels = ""
                        for (String k : keys) {
                          if (sh(returnStdout: true, script: "jq -r '.$k' < ${env.TEMP_MANIFEST_HOME}/manifest.json").trim() == 'null') {
                            if (dels == "")
                              dels = dels + "del(.$k)"
                            else
                              dels = dels + " | del(.$k)"
                          }
                        }
                        if (dels != "") {
                          sh(returnStdout: true, script: "old=\$(cat ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json) && echo \$old | jq -r \'${dels}\' > ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json && echo \$old | jq '.sower = []' > ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json")
                        }
                        sh(returnStdout: true, script: "bs=\$(jq -r .versions < ${env.TEMP_MANIFEST_HOME}/manifest.json) "
                            + "&& google_present=\$(jq 'has(\"google\")' < ${env.TEMP_MANIFEST_HOME}/manifest.json) "
                            + "&& google=\$(jq -r '.google // empty' < ${env.TEMP_MANIFEST_HOME}/manifest.json) "
                            + "&& old=\$(cat ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json) "
                            + """&& echo \$old | jq -r --arg od ${od} --arg pa ${pa} --argjson vs \"\$bs\" --argjson gl \"\$google\""""
                            + " '(.global.dictionary_url) |= \$od"
                            + / | (.global.portal_app) |=/ + "\$pa"
                            + / | (.versions) |=/ + "\$vs"
                            + / | if \$gl != \"\" then (.google |= \$gl) else . end'"  + " > ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json")
                        println(parseSowerBlockOutput)
                        if (parseSowerBlockOutput != "null") {
                          // set Jenkins CI service accounts for sower jobs if the property exists
                          sh(returnStdout: true, script: "cat sower_block.json | jq -r '.[] | if has(\"serviceAccountName\") then .serviceAccountName = \"jobs-${NAMESPACE}-planx-pla-net\" else . end' > new_scv_acct_sower_block.json")
                          String sowerBlock2 = sh(returnStdout: true, script: "cat new_scv_acct_sower_block.json")
                          println(sowerBlock2)
                          sh(returnStdout: true, script: "cat new_scv_acct_sower_block.json | jq -s . > sower_block.json")
                          String sowerBlock3 = sh(returnStdout: true, script: "cat sower_block.json")
                          println(sowerBlock3)
                          sh(returnStdout: true, script: "old=\$(cat ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json) && echo \$old | jq -r --argjson sj \"\$(cat sower_block.json)\" '(.sower) = \$sj' > ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json")
                        }
                        // replace netpolicy
                        sh(returnStdout: true, script: "if [ -f \"netpolicy.json\" ]; then "
                          + "old=\$(cat ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json) && echo \$old | jq -r 'del(.global.netpolicy)' > ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json;"
                          + "fi")
                        // replace Portal block
                        sh(returnStdout: true, script: "if [ -f \"portal_block.json\" ]; then "
                          + "old=\$(cat ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json) && echo \$old | jq -r --argjson sp \"\$(cat portal_block.json)\" '(.portal) = \$sp' > ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json; "
                          + "else "
                          + "jq 'del(.portal)' ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json > manifest_tmp.json && mv manifest_tmp.json ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json; "
                          + "fi")
                        // replace global.frontend_root
                        sh(returnStdout: true, script: "if [ -f \"frontend_root.json\" ]; then "
                          + "old=\$(cat ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json) && echo \$old | jq -r --arg sp \"\$(cat frontend_root.json)\" '.global.frontend_root = \$sp' > ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json; "
                          + "fi")
                        // replace global.es7
                        sh(returnStdout: true, script: "if [ -f \"es7.json\" ]; then "
                          + "old=\$(cat ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json) && echo \$old | jq -r --arg sp \"\$(cat es7.json)\" '.global.es7 = \$sp' > ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json; "
                          + "fi")
                        def manifestMergeBlockKeys = ["ssjdispatcher", "indexd", "metadata", "mariner", "awsstoragegateway"]
                        for (String item : manifestMergeBlockKeys) {
                          sh(returnStdout: true, script: "if [ -f \"${item}_block.json\" ]; then "
                            + "old=\$(cat ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json) && echo \$old | jq -r --argjson sp \"\$(cat ${item}_block.json)\" '(.${item}) = \$sp' > ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json; "
                            + "else "
                            + "jq 'del(.${item})' ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json > manifest_tmp.json && mv manifest_tmp.json ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json; "
                            + "fi")
                        }

                        String rs = sh(returnStdout: true, script: "cat ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json")
                        return rs
                    }
                }
            }
        }
        stage('Overwrite Config Folders') {
            steps {
                script {
                  List<String> folders = sh(returnStdout: true, script: "ls ${env.TEMP_MANIFEST_HOME}").split()
                  if (folders.contains('portal')) {
                    println('Copying all the contents from ${env.TEMP_MANIFEST_HOME}/portal into ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/...')
                    sh(script: "cp -rf ${env.TEMP_MANIFEST_HOME}/portal ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/")

                    // Some commons display a user agreement quiz after logging in for the
                    // first time. This quiz is too customizable to be included in the tests
                    // at the moment. This removes the requiredCerts var from the config so
                    // that NO quizzes will be displayed.
                    config_location = "${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/portal/gitops.json"
                    if (fileExists(config_location)) {
                      sh(script: "sed -i '/\"requiredCerts\":/d' ${config_location}")
                    }
                  }
                  // Aggregate Metadata Config
                  if (folders.contains('metadata')) {
                    println("### Overwrite metadata folder ###")
                    // sh(script: "cp -rf tmpGitClone/$changedDir/metadata ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/")
                    sh(script: "sed -i -E 's#(\"AGG_MDS_NAMESPACE\":).*#\\1 \"${NAMESPACE}\"#' ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifest.json")
                    sh(script: "sed -i -E 's#(\"mds_url\":).*#\\1 \"https://${NAMESPACE}.planx-pla.net\",#' ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/metadata/aggregate_config.json")
                    sh(script: "sed -i -E 's#(\"commons_url\":).*#\\1 \"${NAMESPACE}.planx-pla.net\"#' ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/metadata/aggregate_config.json")
                  }
                  if (folders.contains('etlMapping.yaml')) {
                    println('Copying etl mapping config from ${env.TEMP_MANIFEST_HOME}/etlMapping.yaml into ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/...')
                    sh(script: "cp -rf ${env.TEMP_MANIFEST_HOME}/etlMapping.yaml ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/")
                  }
                  // List manifests folder
                  println("###List manifests folder...")
                  if(folders.contains('manifests')){
                    List<String> manifests_sub_folders = sh(returnStdout: true, script: "ls ${env.TEMP_MANIFEST_HOME}/manifests").split()
                    // Overwrite mariner folder
                    println("###Overwrite  mariner folder...")
                    if(manifests_sub_folders.contains('mariner')){
                      sh(returnStdout: true, script: "cp -rf ${env.TEMP_MANIFEST_HOME}/manifests/mariner ${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifests")
                      sh(returnStdout: true, script: "echo \$(cat ${env.TEMP_MANIFEST_HOME}/manifests/mariner/mariner.json)")
                      // replace s3 bucket
                      println("###Replace s3 bucket in mariner.json...")
                      config_location = "${env.MANIFEST_HOME}/${NAMESPACE}.planx-pla.net/manifests/mariner/mariner.json"
                      sh(returnStdout: true, script: "echo \$(cat ${config_location})")
                      sh(returnStdout: true, script: "jq '.storage.s3.name=\"qaplanetv1--${NAMESPACE}--mariner-707767160287\"' ${config_location} > mariner_tmp.json && mv mariner_tmp.json ${config_location}")
                    }
                  }
                }
            }
        }
        stage('Roll the environment') {
            steps {
                dir("cdis-manifest/${NAMESPACE}.planx-pla.net") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh
                            yes | gen3 reset
                        '''
                    }
                }
            }
        }
        stage('Run usersync') {
            steps {
                dir("cdis-manifest/${NAMESPACE}.planx-pla.net") {
                    script {
                        sh '''#!/bin/bash +x
                            set -e
                            export GEN3_HOME=\$WORKSPACE/cloud-automation
                            export KUBECTL_NAMESPACE=\${NAMESPACE}
                            source $GEN3_HOME/gen3/gen3setup.sh
                            gen3 job run usersync ADD_DBGAP true
                            kubectl -n ${KUBECTL_NAMESPACE} wait --for=condition=complete --timeout=-1s jobs/usersync
                        '''
                    }
                }
            }
        }
    }
}
