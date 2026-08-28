ARG WM_IMAGE=ghcr.io/windmill-labs/windmill:1.775.1

FROM ${WM_IMAGE}

USER root

ENV DAILY_DASH_HOME=/opt/daily-dash
ENV DAILY_DASH_BIN=/opt/daily-dash/.venv/bin/daily-dash

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
