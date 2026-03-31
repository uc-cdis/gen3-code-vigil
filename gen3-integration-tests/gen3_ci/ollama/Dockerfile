ARG AZLINUX_BASE_VERSION=master

FROM quay.io/cdis/amazonlinux-base:${AZLINUX_BASE_VERSION} AS base

# Install curl
RUN dnf install -y --allowerasing \
    curl \
    findutils \
    zstd \
    tar \
    gzip

# Create model directory
WORKDIR /models

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Have ollama create/build the model
RUN bash -c "\
    ollama serve & \
    sleep 5 && \
    ollama pull gemma3:4b \
"

# List ollama model
RUN bash -c "\
    ollama serve & \
    sleep 5 && \
    ollama list \
"

# Show ollama model
RUN bash -c "\
    ollama serve & \
    sleep 5 && \
    ollama show gemma3:4b \
"

# Install kubectl-ai
RUN curl -fsSL https://raw.githubusercontent.com/GoogleCloudPlatform/kubectl-ai/main/install.sh -o install.sh \
    && sed -i 's/sudo //g' install.sh \
    && bash install.sh

# Install Kubectl
RUN curl -LO https://dl.k8s.io/release/v1.33.0/bin/linux/amd64/kubectl && \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Expose the port 11434
EXPOSE 11434

# Run ollama serve command
CMD ["ollama", "serve"]
