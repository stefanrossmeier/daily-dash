ARG WM_IMAGE=ghcr.io/windmill-labs/windmill:1.775.1

FROM ${WM_IMAGE}

USER root

ENV DAILY_DASH_HOME=/opt/daily-dash
ENV DAILY_DASH_BIN=/opt/daily-dash/.venv/bin/daily-dash

# The private data repository is bind-mounted from the host and owned by a
# different uid than the container user, so git refuses to operate on it
# ("dubious ownership"). Windmill job processes get a sanitized environment
# and HOME, so this must be a system-level git config baked into the image —
# env vars or a container-local .gitconfig are not visible to jobs and are
# lost on every rebuild.
RUN git config --system --add safe.directory /data/daily-dash-data

WORKDIR /opt/daily-dash

COPY pyproject.toml uv.lock README.md .python-version ./
COPY src ./src
COPY config ./config
COPY assets /opt/daily-dash/assets

RUN uv sync \
    --frozen \
    --no-dev \
    --python 3.12

WORKDIR /tmp
