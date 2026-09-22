# Used to run load tests in k8s instead of GitHub Actions (allows running tests for longer
# than Github's 6h hard limit).
# Only used for TES tests at the time of writing.

FROM quay.io/cdis/amazonlinux-base:3.13-pythonnginx AS base

ENV appname=gen3-load-tests \
    NODEJS_VERSION=20

WORKDIR /${appname}

RUN chown -R gen3:gen3 /${appname}

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

# copy ONLY the poetry artifacts, so that a change to the source code does not invalidate the
# cached dependency install below
COPY --chown=gen3:gen3 poetry.lock pyproject.toml /${appname}/

# --no-root because the app itself is installed further down, once its sources are in
RUN poetry install -vv --without dev --no-interaction --no-root

# copy the source code only after installing the dependencies
COPY --chown=gen3:gen3 . /${appname}

# Run poetry again so the app itself gets installed too
RUN poetry install --without dev --no-interaction

# Final stage
FROM base

COPY --from=builder /${appname}/.venv /${appname}/.venv
COPY --from=builder /${appname} /${appname}

# Install chromium
RUN apt-get update && poetry run playwright install-deps && poetry run playwright install --with-deps chromium

RUN mkdir output

WORKDIR /${appname}

CMD ["/bin/bash"]
