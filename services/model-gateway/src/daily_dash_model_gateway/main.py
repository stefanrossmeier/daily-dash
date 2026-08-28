from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, Literal

import httpx
import yaml
from fastapi import FastAPI, HTTPException
from jsonschema import ValidationError, validate
from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    run_id: str | None = None
    profile: str | None = None

    messages: list[Message]

    response_schema: dict[str, Any] | None = None
    response_schema_name: str = "daily_dash_response"


class Usage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str
    provider: str
    model: str
    generation_id: str | None = None

    content: Any
    usage: Usage
    latency_ms: int
    attempts: int = 1
    attempt_errors: list[str] = Field(default_factory=list)
    usage_complete: bool = True


def _load_api_key() -> str:
    key_file = os.getenv("OPENROUTER_API_KEY_FILE")

    if key_file:
        value = Path(key_file).read_text(encoding="utf-8").strip()
        if value:
            return value

    value = os.getenv("OPENROUTER_API_KEY", "").strip()
    if value:
        return value

    raise RuntimeError("OpenRouter API key is not configured")


def _load_config() -> dict[str, Any]:
    path = Path(
        os.getenv(
            "MODEL_GATEWAY_CONFIG",
            "/app/config/model-gateway.yaml",
        )
    )

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("invalid model gateway configuration")

    return data


async def _post_openrouter(
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_seconds: float,
) -> httpx.Response:
    try:
        async with asyncio.timeout(timeout_seconds):
            async with httpx.AsyncClient(timeout=None) as client:
                return await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
    except TimeoutError as exc:
        raise httpx.ReadTimeout(
            f"OpenRouter model attempt exceeded {timeout_seconds:.1f}s wall-clock deadline"
        ) from exc


app = FastAPI(title="DailyDash Model Gateway")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    config = _load_config()
    aliases = config.get("aliases", {})

    alias = aliases.get(request.alias)
    if not isinstance(alias, dict):
        raise HTTPException(
            status_code=404,
            detail=f"unknown model alias: {request.alias}",
        )

    if alias.get("provider") != "openrouter":
        raise HTTPException(
            status_code=500,
            detail="unsupported configured provider",
        )

    model = str(alias["model"])
    max_attempts = int(alias.get("max_attempts", 1))
    if max_attempts < 1:
        raise HTTPException(
            status_code=500,
            detail="configured max_attempts must be at least one",
        )

    api_key = _load_api_key()
    attempt_errors: list[str] = []
    request_started = time.monotonic()

    for attempt in range(1, max_attempts + 1):
        payload: dict[str, Any] = {
            "model": model,
            "messages": [message.model_dump() for message in request.messages],
            "usage": {"include": True},
        }

        if request.response_schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": request.response_schema_name,
                    "strict": True,
                    "schema": request.response_schema,
                },
            }

            if alias.get("require_structured_output", True):
                payload["provider"] = {
                    "require_parameters": True,
                }

        try:
            response = await _post_openrouter(
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/stefanrossmeier/daily-dash",
                    "X-Title": "DailyDash",
                },
                payload=payload,
                timeout_seconds=float(alias.get("timeout_seconds", 180)),
            )

            if response.is_error:
                raise RuntimeError(
                    f"OpenRouter returned HTTP {response.status_code}: {response.text}"
                )

            body = response.json()
            content_text = body["choices"][0]["message"]["content"]

            if request.response_schema is not None:
                parsed = json.loads(content_text)
                validate(
                    instance=parsed,
                    schema=request.response_schema,
                )
                content: Any = parsed
            else:
                content = content_text

            usage = body.get("usage") or {}

            return ChatResponse(
                alias=request.alias,
                provider="openrouter",
                model=str(body.get("model") or model),
                generation_id=body.get("id"),
                content=content,
                usage=Usage(
                    input_tokens=int(usage.get("prompt_tokens", 0) or 0),
                    output_tokens=int(usage.get("completion_tokens", 0) or 0),
                    total_tokens=int(usage.get("total_tokens", 0) or 0),
                    cost_usd=float(usage.get("cost", 0.0) or 0.0),
                ),
                latency_ms=int((time.monotonic() - request_started) * 1000),
                attempts=attempt,
                attempt_errors=attempt_errors,
                usage_complete=not attempt_errors,
            )

        except (
            httpx.HTTPError,
            RuntimeError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            ValidationError,
        ) as exc:
            attempt_errors.append(f"attempt {attempt}: {exc}")

    raise HTTPException(
        status_code=502,
        detail=(f"all {max_attempts} attempts failed for {model}: " + " | ".join(attempt_errors)),
    )
