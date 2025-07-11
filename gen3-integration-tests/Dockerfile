FROM python:3.9-slim-bullseye AS base

ENV appname=gen3-integration-tests \
    NODEJS_VERSION=20

WORKDIR /${appname}

# Install pipx
RUN python3 -m pip install --break-system-packages pipx && \
    python3 -m pipx ensurepath

RUN pipx install 'poetry<2.0'

ENV PATH="/root/.local/bin:${PATH}"

#apt update and apt install
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    vim \
    wamerican \
    git \
    jq \
    awscli \
    openjdk-11-jre \
    && rm -rf /var/lib/apt/lists/*

# Install Nodejs 20 and allure
RUN curl -fsSL https://deb.nodesource.com/setup_${NODEJS_VERSION}.x  | bash && \
    apt-get install -y nodejs && \
    npm install -g allure-commandline --save-dev

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl.sha256" && \
    echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check && \
    install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Builder stage
FROM base AS builder

ENV POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_VIRTUALENVS_CREATE=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev \
    libpq-dev \
    curl \
    build-essential \
    gcc \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY poetry.lock pyproject.toml /${appname}/

# Install packages
RUN poetry install --no-interaction

COPY . /${appname}/

# Final stage
FROM base

COPY --from=builder /${appname}/.venv /${appname}/.venv
COPY --from=builder /${appname} /${appname}

# Install chromium
RUN apt-get update && poetry run playwright install-deps && poetry run playwright install --with-deps chromium

RUN mkdir output

WORKDIR /${appname}

CMD ["/bin/bash"]
