ARG AZLINUX_BASE_VERSION=master

FROM quay.io/cdis/amazonlinux-base:${AZLINUX_BASE_VERSION} AS base

ENV appname=gen3-fhir-stub

WORKDIR /${appname}

ADD https://github.com/uc-cdis/gen3-code-vigil/blob/feat/gen3-fhir-proxy/gen3-load-tests/gen3_ci/gen3_fhir_stub/fhir_backend_stub.py .

EXPOSE 8080

CMD ["python", "stub.py"]
