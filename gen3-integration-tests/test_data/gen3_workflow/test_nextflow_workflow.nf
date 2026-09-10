process dicom_to_png {
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
