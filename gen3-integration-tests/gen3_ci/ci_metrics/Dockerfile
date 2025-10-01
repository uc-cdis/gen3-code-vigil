ARG AZLINUX_BASE_VERSION=master

FROM quay.io/cdis/amazonlinux-base:${AZLINUX_BASE_VERSION} AS base

ARG HELM_VERSION=v3.13.0
ARG KUBECTL_VERSION=v1.33.0

# Install required tools including kubectl and aws
RUN dnf install -y --allowerasing \
    curl \
    tar \
    gzip \
    shadow-utils \
    coreutils \
    postgresql \
    awscli

# Install Helm
RUN curl -LO "https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz" && \
    tar -zxvf "helm-${HELM_VERSION}-linux-amd64.tar.gz" && \
    mv linux-amd64/helm /usr/local/bin/helm && \
    rm -rf linux-amd64 "helm-${HELM_VERSION}-linux-amd64.tar.gz"

# Install Kubectl
RUN curl -LO https://dl.k8s.io/release/v1.33.0/bin/linux/amd64/kubectl && \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Create gen3 user
RUN useradd -m -s /bin/bash gen3

# Set working directory and switch to gen3 user
USER gen3
WORKDIR /home/gen3

# Default command
CMD ["bash"]
