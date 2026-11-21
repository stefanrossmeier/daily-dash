from __future__ import annotations

import os
import uuid
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field


def _rank_gateway_token() -> str | None:
    """Bearer token for the dedicated llm-gateway ranking instance. Read from
    a private file (DAILY_DASH_RANK_GATEWAY_TOKEN_FILE) or the environment;
    never logged."""
    path = os.getenv("DAILY_DASH_RANK_GATEWAY_TOKEN_FILE")
    if path:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()
    value = os.getenv("DAILY_DASH_RANK_GATEWAY_TOKEN", "").strip()
    return value or None


class GatewayUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    # Returned by the dedicated llm-gateway instance; the old model gateway
    # omits them and the defaults keep both responses valid.
    reasoning_tokens: int = Field(default=0, ge=0)
    cache_tokens: int = Field(default=0, ge=0)


class GatewayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str
    provider: str
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
        configured_url = (
            base_url or os.getenv("DAILY_DASH_MODEL_GATEWAY_URL") or "http://127.0.0.1:18080"
        )

        self._base_url = configured_url.rstrip("/")
        # Ranking chats route to daily-dash's dedicated llm-gateway instance
        # when configured; X search keeps the shared model gateway (native X
        # stays disabled on the llm-gateway release). Both speak the same
        # /v1/chat wire, so the split is URL-level only.
        self._rank_url = (os.getenv("DAILY_DASH_RANK_GATEWAY_URL") or self._base_url).rstrip("/")
        self._rank_token = _rank_gateway_token()
        self._timeout_seconds = timeout_seconds

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
        headers = {}
        if self._rank_url != self._base_url and self._rank_token:
            # The llm-gateway wire authenticates the project principal and
            # recovers requests by stable logical ID, so retries stay free.
            headers = {
                "Authorization": f"Bearer {self._rank_token}",
                "Idempotency-Key": f"daily-dash:{uuid.uuid4()}",
            }
        response = httpx.post(
            f"{self._rank_url}/v1/chat",
            json={
                "alias": alias,
                "purpose": purpose,
                "profile": profile,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_schema_name": response_schema_name,
                "response_schema": response_schema,
            },
            headers=headers,
            timeout=self._timeout_seconds,
        )

        if response.is_error:
            raise RuntimeError(
                f"model gateway returned HTTP {response.status_code}: {response.text}"
            )

        return GatewayResponse.model_validate(response.json())

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
        response = httpx.post(
            f"{self._base_url}/v1/x-search",
            json={
                "alias": alias,
                "purpose": purpose,
                "profile": profile,
                "input": input_text,
                "allowed_x_handles": allowed_x_handles,
                "from_date": from_date,
                "to_date": to_date,
                "response_schema_name": response_schema_name,
                "response_schema": response_schema,
            },
            timeout=self._timeout_seconds,
        )

        if response.is_error:
            raise RuntimeError(
                f"model gateway returned HTTP {response.status_code}: {response.text}"
            )

        return GatewayResponse.model_validate(response.json())
