# Used to run load tests in k8s instead of GitHub Actions (allows running tests for longer
# than Github's 6h hard limit).
# Only used for TES tests at the time of writing.

ARG AZLINUX_BASE_VERSION=3.13-pythonpoetry

FROM quay.io/cdis/amazonlinux-base:${AZLINUX_BASE_VERSION} AS base

ENV appname=gen3-load-tests \
    NODEJS_VERSION=24

WORKDIR /${appname}

RUN chown -R gen3:gen3 /${appname}

# # Install pipx
# RUN python3 -m pip install --break-system-packages pipx && \
#     python3 -m pipx ensurepath

# RUN pipx install 'poetry<2.0'

# ENV PATH="/root/.local/bin:${PATH}"

USER root
RUN dnf install -y gcc python3-devel curl jq && dnf clean all
USER gen3

# # Install Nodejs and allure
# RUN curl -fsSL https://rpm.nodesource.com/setup_22.x | sudo bash - && \
#     dnf install -y nodejs && \
#     npm install -g allure-commandline --save-dev
# # RUN curl -fsSL https://deb.nodesource.com/setup_${NODEJS_VERSION}.x  | bash && \
# #     dnf install -y nodejs && \
# #     npm install -g allure-commandline --save-dev

# # Install kubectl
# RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && \
#     curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl.sha256" && \
#     echo "$(cat kubectl.sha256)  kubectl" | sha256sum --check && \
#     install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

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

# USER root
# poetry installs the app as an editable package, so /venv holds a .pth pointing back at this
# source tree: both are needed at runtime.
COPY --from=builder /venv /venv
COPY --from=builder /${appname} /${appname}

# Install chromium
# RUN poetry run playwright install-deps && poetry run playwright install #--with-deps chromium
# USER gen3

# RUN mkdir output

WORKDIR /${appname}

CMD ["bash"]
