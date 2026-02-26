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

# Download model
RUN curl -L -O https://huggingface.co/unsloth/Qwen3-4B-Thinking-2507-GGUF/tree/main/Qwen3-4B-Thinking-2507-Q4_K_M.gguf

# Create model file
RUN echo 'FROM /models/Qwen3-4B-Thinking-2507-Q4_K_M.gguf' > Modelfile

# Have ollama create/build the model
RUN bash -c "\
    ollama serve & \
    sleep 5 && \
    ollama create qwen3:4b -f Modelfile \
"

# List ollama models
RUN bash -c "\
    ollama serve & \
    sleep 5 && \
    ollama list \
"

# Remove GGUF file from /models
RUN rm Qwen3-4B-Thinking-2507-Q4_K_M.gguf

# Expose the port 11434
EXPOSE 11434

# Run ollama serve command
CMD ["ollama", "serve"]
