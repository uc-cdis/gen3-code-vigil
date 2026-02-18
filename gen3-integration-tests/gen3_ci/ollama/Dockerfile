ARG AZLINUX_BASE_VERSION=master

FROM quay.io/cdis/amazonlinux-base:${AZLINUX_BASE_VERSION} AS base

# Install wget
RUN dnf install -y --allowerasing \
    wget

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Create model directory
WORKDIR /models

# Download model
RUN wget https://huggingface.co/unsloth/gemma-3-4b-it-GGUF/resolve/main/gemma-3-4b-it-Q4_K_M.gguf

# Create model file
RUN echo 'FROM /models/gemma-3-4b-it-Q4_K_M.gguf' > Modelfile

# Have ollama create/build the model
RUN bash -c "\
    ollama serve & \
    sleep 5 && \
    ollama create gemma:4b -f Modelfile \
"

# Remove GGUF file
RUN rm gemma-3-4b-it-Q4_K_M.gguf

# Expose the port 11434
EXPOSE 11434

# Run ollama serve command
CMD ["ollama", "serve"]
