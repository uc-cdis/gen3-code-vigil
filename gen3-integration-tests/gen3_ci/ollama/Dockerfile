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
RUN curl -L -O https://huggingface.co/unsloth/gemma-3-4b-it-GGUF/resolve/main/gemma-3-4b-it-Q4_K_M.gguf

# Create model file
RUN echo 'FROM /models/gemma-3-4b-it-Q4_K_M.gguf' > Modelfile

# Have ollama create/build the model
RUN bash -c "\
    ollama serve & \
    sleep 5 && \
    ollama create gemma:4b -f Modelfile \
"

# List ollama model
RUN bash -c "\
    ollama serve & \
    sleep 5 && \
    ollama list \
"

# Remove GGUF file from /models
RUN rm gemma-3-4b-it-Q4_K_M.gguf

# Expose the port 11434
EXPOSE 11434

# Run ollama serve command
CMD ["ollama", "serve"]
