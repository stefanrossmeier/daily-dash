from __future__ import annotations

import hashlib
import json
import os
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field


def _idempotency_key(body: dict[str, object]) -> str:
    """Stable logical-request ID: identical request bodies reuse one key.

    A caller-level retry must replay the gateway's recorded result instead of
    being charged again, so the key is derived from the request content — a
    fresh random key per call would make every retry a new paid request.
    """
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
    return f"daily-dash:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


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
        configured_url = (
            base_url or os.getenv("DAILY_DASH_MODEL_GATEWAY_URL") or "http://127.0.0.1:18080"
        )

        self._base_url = configured_url.rstrip("/")
        # Ranking chats AND native X search route to daily-dash's dedicated
        # llm-gateway instance when configured (its /v1/chat and /v1/x-search
        # dashboard-compatibility wires). The shared model gateway stays the
        # fallback when no instance URL is configured; both speak the same
        # wire, so the split is URL-level only.
        self._rank_url = (os.getenv("DAILY_DASH_RANK_GATEWAY_URL") or self._base_url).rstrip("/")
        self._rank_token = _rank_gateway_token()
        self._timeout_seconds = timeout_seconds

    def _headers(self, body: dict[str, object]) -> dict[str, str]:
        """Bearer auth plus a stable Idempotency-Key for the instance wires."""
        if self._rank_url == self._base_url or not self._rank_token:
            return {}
        return {
            "Authorization": f"Bearer {self._rank_token}",
            "Idempotency-Key": _idempotency_key(body),
        }

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
        response = httpx.post(
            f"{self._rank_url}/v1/chat",
            json=body,
            headers=self._headers(body),
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
        # Native X search runs on the same dedicated llm-gateway instance as
        # ranking (its /v1/x-search wire).
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
        response = httpx.post(
            f"{self._rank_url}/v1/x-search",
            json=body,
            headers=self._headers(body),
            timeout=self._timeout_seconds,
        )

        if response.is_error:
            raise RuntimeError(
                f"model gateway returned HTTP {response.status_code}: {response.text}"
            )

        return GatewayResponse.model_validate(response.json())
