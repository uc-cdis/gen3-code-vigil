#!/usr/bin/env nextflow

process TEST_GPU {
    tag "task-${id}"

    container 'pytorch/pytorch:latest'
    conda 'pytorch::pytorch=2.5.1 pytorch::torchvision=0.20.1 nvidia::cuda=12.1'
    accelerator 1
    memory '1G'

    input:
    val id

    output:
        stdout

    script:
    """
    #!/usr/bin/env python
    import torch

    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        cuda_version = torch.version.cuda
        print(f"GPU: {gpu_name}")
        print(f"CUDA Version: {cuda_version}")
    else:
        raise RuntimeError("CUDA is not available on this system.")
    """
}

workflow {
    Channel.from(1..params.n_tasks) | TEST_GPU
}
