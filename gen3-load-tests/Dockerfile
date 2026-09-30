# Used to run load tests in k8s instead of GitHub Actions (allows running tests for longer
# than Github's 6h hard limit).
# Only used for TES tests at the time of writing.

ARG AZLINUX_BASE_VERSION=3.13-pythonpoetry

FROM quay.io/cdis/amazonlinux-base:${AZLINUX_BASE_VERSION} AS base

ENV appname=gen3-load-tests \
    NODEJS_VERSION=24

WORKDIR /${appname}

RUN chown -R gen3:gen3 /${appname}

# switch to root user to install packages
USER root

RUN dnf install -y gcc python3-devel jq unzip \
    java-21-amazon-corretto-headless \
    && dnf clean all

RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install && \
    rm -rf awscliv2.zip ./aws

USER gen3

# Builder stage
FROM base AS builder

# copy ONLY the poetry artifacts, so that a change to the source code does not invalidate the
# cached dependency install below
COPY --chown=gen3:gen3 poetry.lock pyproject.toml /${appname}/

# --no-root because the app itself is installed further down, once its sources are in
USER root
RUN poetry install -vv --without dev --no-interaction --no-root
USER gen3

# copy the source code only after installing the dependencies
COPY --chown=gen3:gen3 . /${appname}

# Run poetry again so the app itself gets installed too
RUN poetry install --without dev --no-interaction

# Final stage
FROM base

# poetry installs the app as an editable package, so /venv holds a .pth pointing back at this
# source tree: both are needed at runtime.
COPY --from=builder /venv /venv
COPY --from=builder /${appname} /${appname}

WORKDIR /${appname}

# this step ensures Nextflow downloads everything it needs now, instead of at runtime when internet
# access may be restricted
RUN nextflow info

CMD ["bash"]
