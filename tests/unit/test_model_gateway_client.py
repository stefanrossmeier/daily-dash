from __future__ import annotations

from typing import Any

from daily_dash.llm.gateway import ModelGatewayClient


class _Response:
    is_error = False
    status_code = 200
    text = ""

    def json(self) -> dict[str, object]:
        return {
            "alias": "rank-budget",
            "provider": "openrouter",
            "model": "test/model",
            "generation_id": "gen-test",
            "content": {"evaluations": {}},
            "usage": {
                "input_tokens": 1,
                "output_tokens": 1,
                "total_tokens": 2,
                "cost_usd": 0.0,
            },
            "latency_ms": 1,
        }


def test_model_gateway_client_default_timeout_covers_two_retries(
    monkeypatch: Any,
) -> None:
    observed_timeout: float | None = None

    def fake_post(*args: object, **kwargs: object) -> _Response:
        nonlocal observed_timeout
        del args
        value = kwargs.get("timeout")
        assert isinstance(value, float)
        observed_timeout = value
        return _Response()

    monkeypatch.setattr("daily_dash.llm.gateway.httpx.post", fake_post)

    ModelGatewayClient("http://gateway.test").chat_structured(
        alias="rank-budget",
        purpose="ranking",
        profile="news-top",
        system="system",
        user="user",
        response_schema_name="test_schema",
        response_schema={"type": "object"},
    )

    assert observed_timeout == 600.0


def test_x_search_client_sends_only_gateway_contract(monkeypatch: Any) -> None:
    observed_url: str | None = None
    observed_json: dict[str, object] | None = None

    def fake_post(*args: object, **kwargs: object) -> _Response:
        nonlocal observed_url, observed_json
        assert args
        assert isinstance(args[0], str)
        observed_url = args[0]
        payload = kwargs.get("json")
        assert isinstance(payload, dict)
        observed_json = payload
        return _Response()

    monkeypatch.setattr("daily_dash.llm.gateway.httpx.post", fake_post)

    ModelGatewayClient("http://gateway.test").x_search_structured(
        alias="x-retrieve",
        purpose="x-retrieval-compatibility",
        profile="x-watchlist-spike",
        input_text="search X",
        allowed_x_handles=["NickTimiraos"],
        from_date="2026-08-28",
        to_date="2026-08-29",
        response_schema_name="x_schema",
        response_schema={"type": "object"},
    )

    assert observed_url == "http://gateway.test/v1/x-search"
    assert observed_json is not None
    assert observed_json["alias"] == "x-retrieve"
    assert observed_json["allowed_x_handles"] == ["NickTimiraos"]
    assert "model" not in observed_json
    assert "plugins" not in observed_json
    assert "x_search_filter" not in observed_json


def test_rank_gateway_env_splits_chat_from_x_search(monkeypatch: Any, tmp_path: Any) -> None:
    """Ranking chats route to the dedicated llm-gateway instance with Bearer
    auth and an Idempotency-Key; X search keeps the model gateway URL."""
    monkeypatch.setenv("DAILY_DASH_MODEL_GATEWAY_URL", "http://model-gateway:8080")
    monkeypatch.setenv("DAILY_DASH_RANK_GATEWAY_URL", "http://daily-dash-llm-gateway:8080")
    token_file = tmp_path / "gateway.token"
    token_file.write_text("synthetic-token\n")
    monkeypatch.setenv("DAILY_DASH_RANK_GATEWAY_TOKEN_FILE", str(token_file))

    observed: dict[str, object] = {}

    def fake_post(
        url: str,
        *,
        json: dict[str, object],
        headers: dict[str, str] | None = None,
        **kw: object,
    ) -> _Response:
        observed["url"] = url
        observed["headers"] = headers or {}
        return _Response()

    monkeypatch.setattr("daily_dash.llm.gateway.httpx.post", fake_post)

    client = ModelGatewayClient()
    client.chat_structured(
        alias="rank-cheap",
        purpose="ranking",
        profile="news-top",
        system="system",
        user="user",
        response_schema_name="test_schema",
        response_schema={"type": "object"},
    )

    assert observed["url"] == "http://daily-dash-llm-gateway:8080/v1/chat"
    headers = observed["headers"]
    assert headers["Authorization"] == "Bearer synthetic-token"
    assert headers["Idempotency-Key"].startswith("daily-dash:")

    client.x_search_structured(
        alias="x-retrieve",
        purpose="retrieval",
        profile="x-watchlist",
        input_text="query",
        allowed_x_handles=["test"],
        from_date="2026-11-21",
        to_date="2026-11-22",
        response_schema_name="test_schema",
        response_schema={"type": "object"},
    )

    # Native X search rides the same dedicated instance as ranking.
    assert observed["url"] == "http://daily-dash-llm-gateway:8080/v1/x-search"
    assert observed["headers"]["Authorization"] == "Bearer synthetic-token"
    assert observed["headers"]["Idempotency-Key"].startswith("daily-dash:")
