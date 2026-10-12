ARG AZLINUX_BASE_VERSION=master

FROM quay.io/cdis/amazonlinux-base:${AZLINUX_BASE_VERSION} AS base

ENV appname=gen3-fhir-stub

WORKDIR /${appname}

COPY fhir_backend_stub.py .

EXPOSE 8080

CMD ["python", "stub.py"]
