FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

COPY services/model-gateway/pyproject.toml \
     services/model-gateway/uv.lock \
     ./

COPY services/model-gateway/src ./src
COPY config/model-gateway.yaml ./config/model-gateway.yaml

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}"
ENV MODEL_GATEWAY_CONFIG="/app/config/model-gateway.yaml"

EXPOSE 8080

CMD ["uvicorn", "daily_dash_model_gateway.main:app", "--host", "0.0.0.0", "--port", "8080"]
