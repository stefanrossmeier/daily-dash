from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field


def _run_id() -> str:
    value = next(
        (
            os.environ[k]
            for k in ("DAILY_DASH_RUN_ID", "WM_ROOT_FLOW_JOB_ID", "WM_JOB_ID")
            if os.getenv(k)
        ),
        None,
    )
    if not value:
        raise RuntimeError(
            "Set DAILY_DASH_RUN_ID for a new logical run; reuse it after interruption"
        )
    return value


def _idempotency_key(body: Mapping[str, object]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return "daily-dash:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _rank_gateway_token() -> str | None:
    """Bearer token for the dedicated llm-gateway ranking instance. Read from
    a private file (DAILY_DASH_GATEWAY_TOKEN_FILE) or the environment;
    never logged."""
    path = os.getenv("DAILY_DASH_GATEWAY_TOKEN_FILE")
    if path:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()
    value = os.getenv("DAILY_DASH_GATEWAY_TOKEN", "").strip()
    return value or None


class GatewayUsage(BaseModel):
    x_posts_fetched: int | None = Field(default=None, ge=0)
    x_profiles_fetched: int | None = Field(default=None, ge=0)
    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    reasoning_tokens: int | None = Field(default=None, ge=0)
    cache_tokens: int | None = Field(default=None, ge=0)


class GatewayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str
    # The dedicated llm-gateway instance leaves provider null when the
    # upstream does not report one (OpenRouter x-search wires).
    provider: str | None = None
    model: str
    generation_id: str | None = None
    content: dict[str, object]
    usage: GatewayUsage
    latency_ms: int = Field(ge=0)
    attempts: int = Field(default=1, ge=1)
    attempt_errors: list[str] = Field(default_factory=list)
    usage_complete: bool = True
    provider_metadata: dict[str, object] = Field(default_factory=dict)


class StructuredChatClient(Protocol):
    def chat_structured(
        self,
        *,
        alias: str,
        purpose: str,
        profile: str,
        system: str,
        user: str,
        response_schema_name: str,
        response_schema: dict[str, object],
    ) -> GatewayResponse: ...


class ModelGatewayClient:
    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout_seconds: float = 600.0,
    ) -> None:
        configured_url = base_url or os.getenv("DAILY_DASH_GATEWAY_URL") or "http://127.0.0.1:18181"
        self._base_url = configured_url.rstrip("/")
        self._token = _rank_gateway_token()
        self._timeout_seconds = timeout_seconds

    def _headers(self, body: Mapping[str, object]) -> dict[str, str]:
        if not self._token:
            raise RuntimeError(
                "DAILY_DASH_GATEWAY_TOKEN_FILE or DAILY_DASH_GATEWAY_TOKEN is required"
            )
        return {"Authorization": f"Bearer {self._token}", "Idempotency-Key": _idempotency_key(body)}

    def _request(self, route: str, body: Mapping[str, object]) -> GatewayResponse:
        body = {**body, "run_id": _run_id()}
        headers = self._headers(body)
        try:
            response = httpx.post(
                f"{self._base_url}/v1/{route}",
                json=body,
                headers=headers,
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError:
            # Recover the same invocation; never start another paid attempt.
            identifier = headers["Idempotency-Key"]
            try:
                response = httpx.get(
                    f"{self._base_url}/v1/requests/{identifier}?format=dashboard",
                    headers=headers,
                    timeout=10,
                )
            except httpx.HTTPError:
                raise RuntimeError(
                    f"gateway transport lost; recover request {identifier}"
                ) from None
        if response.is_error or response.status_code == 202:
            raise RuntimeError(
                f"gateway HTTP {response.status_code}; request {headers['Idempotency-Key']}"
            )
        return GatewayResponse.model_validate(response.json())

    def chat_structured(
        self,
        *,
        alias: str,
        purpose: str,
        profile: str,
        system: str,
        user: str,
        response_schema_name: str,
        response_schema: dict[str, object],
    ) -> GatewayResponse:
        body = {
            "alias": alias,
            "purpose": purpose,
            "profile": profile,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_schema_name": response_schema_name,
            "response_schema": response_schema,
        }
        return self._request("chat", body)

    def x_search_structured(
        self,
        *,
        alias: str,
        purpose: str,
        profile: str,
        input_text: str,
        allowed_x_handles: list[str],
        from_date: str,
        to_date: str,
        response_schema_name: str,
        response_schema: dict[str, object],
    ) -> GatewayResponse:
        body = {
            "alias": alias,
            "purpose": purpose,
            "profile": profile,
            "input": input_text,
            "allowed_x_handles": allowed_x_handles,
            "from_date": from_date,
            "to_date": to_date,
            "response_schema_name": response_schema_name,
            "response_schema": response_schema,
        }
        return self._request("x-search", body)
