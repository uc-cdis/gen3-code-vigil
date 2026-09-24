process dicom_to_png {
	// Dockerfile location: https://github.com/uc-cdis/bio-nextflow/tree/c8f9fd595135078b1ac1b365aa3393641b5cacdb/nextflow_notebooks/containerized_cpu_workflows/midrc_batch_demo
	container 'quay.io/cdis/gen3-workflow:integration_tests_dicom_image'

    publishDir 'results'

    input:
    path dicom_files

    output:
    stdout emit: dicom_to_png_log
    path('outputs/*.png')

    script:
    """
    python3 /utils/dicom_to_png.py $dicom_files
    mkdir -p outputs
    cp *.png outputs/
    """
}

process extract_metadata {
	container 'quay.io/cdis/gen3-workflow:integration_tests_dicom_image'

    publishDir 'results'

    input:
    path dicom_files

    output:
    stdout emit: extract_metadata_log
    path('*.csv'), emit: csv_files

    script:
    """
    python3 /utils/extract_metadata.py $dicom_files
    """
}

workflow {
    dicom_data = "$baseDir/input_data/*.dcm"
    dicom_files = Channel.fromPath(dicom_data)
    dicom_to_png(dicom_files)
    extract_metadata(dicom_files)
}
