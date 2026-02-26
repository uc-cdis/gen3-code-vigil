ARG AZLINUX_BASE_VERSION=master

FROM quay.io/cdis/amazonlinux-base:${AZLINUX_BASE_VERSION} AS base

# Install curl
RUN dnf install -y --allowerasing \
    curl \
    findutils \
    zstd \
    tar

# Create model directory
WORKDIR /models

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Have ollama create/build the model
RUN bash -c "\
    ollama serve & \
    sleep 5 && \
    ollama pull qwen3:4b \
"

# List ollama models
RUN bash -c "\
    ollama serve & \
    sleep 5 && \
    ollama list \
"

# Show ollama models
RUN bash -c "\
    ollama serve & \
    sleep 5 && \
    ollama show qwen3:4b \
"

# Expose the port 11434
EXPOSE 11434

# Run ollama serve command
CMD ["ollama", "serve"]
