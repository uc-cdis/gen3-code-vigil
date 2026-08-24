#!/usr/bin/env nextflow

nextflow.enable.dsl=2

process HELLO_TASK {
    tag "task-${id}"

    input:
    val id

    publishDir "results"
    output:
      path "output-${id}.txt"

    script:
    """
    echo "Hello from task ${id}" > output-${id}.txt
    """
}

workflow {
  Channel.from(1..params.n_tasks) | HELLO_TASK
}
