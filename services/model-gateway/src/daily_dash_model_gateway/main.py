from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import date
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


class XSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    run_id: str | None = None
    profile: str | None = None

    input: str = Field(min_length=1)
    allowed_x_handles: list[str] = Field(min_length=1, max_length=20)
    from_date: date
    to_date: date

    response_schema: dict[str, Any]
    response_schema_name: str = "daily_dash_x_search_response"


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
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


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


async def _post_openrouter_responses(
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_seconds: float,
) -> httpx.Response:
    try:
        async with asyncio.timeout(timeout_seconds):
            async with httpx.AsyncClient(timeout=None) as client:
                return await client.post(
                    "https://openrouter.ai/api/v1/responses",
                    headers=headers,
                    json=payload,
                )
    except TimeoutError as exc:
        raise httpx.ReadTimeout(
            f"OpenRouter model attempt exceeded {timeout_seconds:.1f}s wall-clock deadline"
        ) from exc


def _decode_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise RuntimeError("OpenRouter Responses output text was empty")

    try:
        decoded = json.loads(stripped)
    except json.JSONDecodeError as direct_error:
        decoder = json.JSONDecoder()
        for index, char in enumerate(stripped):
            if char != "{":
                continue
            try:
                decoded, _ = decoder.raw_decode(stripped[index:])
            except json.JSONDecodeError:
                continue
            break
        else:
            preview = stripped[:240].replace("\n", "\\n")
            raise RuntimeError(
                "OpenRouter Responses output was not valid JSON "
                f"({direct_error.msg} at line {direct_error.lineno} column {direct_error.colno}); "
                f"output_prefix={preview!r}"
            ) from direct_error

    if not isinstance(decoded, dict):
        raise RuntimeError("OpenRouter Responses structured output was not a JSON object")
    return decoded


def _decode_http_json(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except json.JSONDecodeError as exc:
        content_type = response.headers.get("content-type", "")
        preview = response.text[:400].replace("\n", "\\n")
        raise RuntimeError(
            "OpenRouter returned a non-JSON Responses body "
            f"(HTTP {response.status_code}, content-type={content_type!r}, body_prefix={preview!r})"
        ) from exc
    if not isinstance(body, dict):
        raise RuntimeError("OpenRouter response was not a JSON object")
    return body


def _extract_responses_output_text(body: dict[str, Any]) -> str:
    direct = body.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    output = body.get("output")
    if not isinstance(output, list):
        raise RuntimeError("OpenRouter Responses result did not contain output text")

    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for content_item in content:
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())

    if not parts:
        raise RuntimeError("OpenRouter Responses result did not contain output text")
    return "\n".join(parts)


def _compact_x_provider_metadata(body: dict[str, Any]) -> dict[str, Any]:
    output = body.get("output")
    search_calls: list[dict[str, Any]] = []
    citation_urls: list[str] = []
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "web_search_call":
                action = item.get("action")
                query = action.get("query") if isinstance(action, dict) else None
                search_calls.append(
                    {
                        "id": item.get("id"),
                        "status": item.get("status"),
                        "query": query,
                    }
                )
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if not isinstance(content_item, dict):
                    continue
                annotations = content_item.get("annotations")
                if not isinstance(annotations, list):
                    continue
                for annotation in annotations:
                    if not isinstance(annotation, dict):
                        continue
                    if annotation.get("type") != "url_citation":
                        continue
                    url = annotation.get("url")
                    if isinstance(url, str) and url.startswith("https://x.com/"):
                        citation_urls.append(url)

    router = body.get("openrouter_metadata")
    compact_router: dict[str, Any] | None = None
    if isinstance(router, dict):
        compact_router = {
            key: router.get(key)
            for key in ("requested", "strategy", "region", "summary", "attempt", "is_byok")
            if key in router
        }
        endpoints = router.get("endpoints")
        if isinstance(endpoints, dict):
            available = endpoints.get("available")
            if isinstance(available, list):
                selected = next(
                    (item for item in available if isinstance(item, dict) and item.get("selected")),
                    None,
                )
                if isinstance(selected, dict):
                    compact_router["selected_endpoint"] = {
                        "provider": selected.get("provider"),
                        "model": selected.get("model"),
                    }

    usage = body.get("usage")
    cost_details = usage.get("cost_details") if isinstance(usage, dict) else None
    unique_citations = list(dict.fromkeys(citation_urls))
    return {
        "openrouter_metadata": compact_router,
        "x_search_call_count": len(search_calls),
        "x_search_queries": [
            str(item["query"]) for item in search_calls if isinstance(item.get("query"), str)
        ],
        "x_search_calls": search_calls,
        "citation_urls": unique_citations,
        "cost_details": cost_details if isinstance(cost_details, dict) else None,
    }


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


@app.post("/v1/x-search", response_model=ChatResponse)
async def x_search(request: XSearchRequest) -> ChatResponse:
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

    if not bool(alias.get("allow_x_search", False)):
        raise HTTPException(
            status_code=403,
            detail=f"model alias is not allowed to use X search: {request.alias}",
        )

    if request.to_date < request.from_date:
        raise HTTPException(
            status_code=400,
            detail="to_date must be on or after from_date",
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
            "input": request.input,
            "plugins": [{"id": "web", "engine": "native"}],
            "x_search_filter": {
                "allowed_x_handles": request.allowed_x_handles,
                "from_date": request.from_date.isoformat(),
                "to_date": request.to_date.isoformat(),
            },
            "reasoning": {"enabled": False},
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": request.response_schema_name,
                    "strict": True,
                    "schema": request.response_schema,
                }
            },
        }
        if alias.get("require_structured_output", True):
            payload["provider"] = {"require_parameters": True}

        try:
            response = await _post_openrouter_responses(
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/stefanrossmeier/daily-dash",
                    "X-Title": "DailyDash",
                    "X-OpenRouter-Metadata": "enabled",
                },
                payload=payload,
                timeout_seconds=float(alias.get("timeout_seconds", 180)),
            )

            if response.is_error:
                raise RuntimeError(
                    f"OpenRouter returned HTTP {response.status_code}: {response.text}"
                )

            body = _decode_http_json(response)
            if body.get("error"):
                raise RuntimeError(f"OpenRouter Responses returned error payload: {body['error']}")
            status = body.get("status")
            if isinstance(status, str) and status not in {"completed", "complete"}:
                raise RuntimeError(
                    "OpenRouter Responses did not complete successfully: "
                    f"status={status!r}, incomplete_details={body.get('incomplete_details')!r}"
                )

            content_text = _extract_responses_output_text(body)
            parsed = _decode_json_object(content_text)
            validate(instance=parsed, schema=request.response_schema)

            usage = body.get("usage") or {}
            if not isinstance(usage, dict):
                usage = {}

            provider_metadata = _compact_x_provider_metadata(body)

            return ChatResponse(
                alias=request.alias,
                provider="openrouter",
                model=str(body.get("model") or model),
                generation_id=body.get("id"),
                content=parsed,
                usage=Usage(
                    input_tokens=int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0),
                    output_tokens=int(
                        usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
                    ),
                    total_tokens=int(usage.get("total_tokens", 0) or 0),
                    cost_usd=float(usage.get("cost", 0.0) or 0.0),
                ),
                latency_ms=int((time.monotonic() - request_started) * 1000),
                attempts=attempt,
                attempt_errors=attempt_errors,
                usage_complete=not attempt_errors,
                provider_metadata=provider_metadata,
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
