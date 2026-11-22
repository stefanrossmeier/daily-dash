from __future__ import annotations

from typing import Any

import httpx
import pytest

from daily_dash.llm.gateway import GatewayResponse, ModelGatewayClient


class Response:
    is_error = False
    status_code = 200

    def json(self) -> dict:
        return {
            "alias": "rank-cheap",
            "provider": "openrouter",
            "model": "test/model",
            "content": {},
            "usage": {"cost_usd": None, "reasoning_tokens": None, "cache_tokens": None},
            "latency_ms": 1,
            "usage_complete": False,
        }


@pytest.fixture(autouse=True)
def credentials(monkeypatch: Any) -> None:
    monkeypatch.setenv("DAILY_DASH_GATEWAY_TOKEN", "synthetic-token")
    monkeypatch.setenv("DAILY_DASH_RUN_ID", "durable-job-one")


def chat(client: ModelGatewayClient) -> GatewayResponse:
    return client.chat_structured(
        alias="rank-cheap",
        purpose="rank",
        profile="news-top",
        system="system",
        user="user",
        response_schema_name="schema",
        response_schema={"type": "object"},
    )


def test_restart_keeps_identity_and_a_new_run_gets_a_new_identity(monkeypatch: Any) -> None:
    calls: list[dict] = []

    def post(url: str, **kw: Any) -> Response:
        calls.append({"url": url, **kw})
        return Response()

    monkeypatch.setattr("daily_dash.llm.gateway.httpx.post", post)
    chat(ModelGatewayClient("http://gateway.test"))
    chat(ModelGatewayClient("http://gateway.test"))
    assert calls[0]["headers"] == calls[1]["headers"]
    assert calls[0]["json"]["run_id"] == "durable-job-one"
    assert calls[0]["headers"]["Authorization"] == "Bearer synthetic-token"
    assert calls[0]["timeout"] == 600.0
    monkeypatch.setenv("DAILY_DASH_RUN_ID", "new-job")
    chat(ModelGatewayClient("http://gateway.test"))
    assert calls[-1]["headers"]["Idempotency-Key"] != calls[0]["headers"]["Idempotency-Key"]


def test_lost_response_recovers_same_request_without_second_post(monkeypatch: Any) -> None:
    calls: list[str] = []

    def post(*a: Any, **kw: Any) -> Response:
        calls.append(kw["headers"]["Idempotency-Key"])
        raise httpx.ReadTimeout("lost response")

    def get(url: str, **kw: Any) -> Response:
        assert url.endswith(f"/v1/requests/{calls[0]}?format=dashboard")
        return Response()

    monkeypatch.setattr("daily_dash.llm.gateway.httpx.post", post)
    monkeypatch.setattr("daily_dash.llm.gateway.httpx.get", get)
    result = chat(ModelGatewayClient("http://gateway.test"))
    assert len(calls) == 1 and result.usage.cost_usd is None
    assert result.usage.reasoning_tokens is None and result.usage.cache_tokens is None


def test_x_uses_same_authenticated_gateway(monkeypatch: Any) -> None:
    def post(url: str, **kw: Any) -> Response:
        assert url == "http://gateway.test/v1/x-search"
        assert kw["headers"]["Authorization"] == "Bearer synthetic-token"
        assert "model" not in kw["json"] and "plugins" not in kw["json"]
        return Response()

    monkeypatch.setattr("daily_dash.llm.gateway.httpx.post", post)
    ModelGatewayClient("http://gateway.test").x_search_structured(
        alias="x-retrieve",
        purpose="retrieve",
        profile="x-watchlist",
        input_text="search",
        allowed_x_handles=["test"],
        from_date="2026-11-21",
        to_date="2026-11-22",
        response_schema_name="schema",
        response_schema={"type": "object"},
    )


def test_missing_credentials_or_run_identity_fails_before_transport(monkeypatch: Any) -> None:
    monkeypatch.delenv("DAILY_DASH_GATEWAY_TOKEN")
    with pytest.raises(RuntimeError, match="TOKEN"):
        chat(ModelGatewayClient())
    monkeypatch.setenv("DAILY_DASH_GATEWAY_TOKEN", "synthetic-token")
    for name in ("DAILY_DASH_RUN_ID", "WM_ROOT_FLOW_JOB_ID", "WM_JOB_ID"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="RUN_ID"):
        chat(ModelGatewayClient())
