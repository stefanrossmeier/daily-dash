from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from daily_dash.experiments.grok_x_search import (
    X_SEARCH_RESPONSE_SCHEMA,
    build_artifact,
    build_gateway_request,
    default_date_range,
)
from daily_dash.llm.gateway import GatewayResponse, GatewayUsage
from daily_dash.prompts.loader import load_prompt_asset

ASSETS = Path("assets")


def _prompt():
    return load_prompt_asset(
        "x-watchlist-retrieval",
        "v4",
        "x-watchlist",
        assets_dir=ASSETS,
    )


def test_build_gateway_request_contains_only_gateway_x_search_contract() -> None:
    payload = build_gateway_request(
        alias="x-retrieve",
        prompt=_prompt(),
        handle="NickTimiraos",
        from_date=date(2026, 8, 28),
        to_date=date(2026, 8, 29),
    )

    assert payload["alias"] == "x-retrieve"
    assert payload["allowed_x_handles"] == ["NickTimiraos"]
    assert payload["from_date"] == "2026-08-28"
    assert payload["to_date"] == "2026-08-29"
    assert payload["response_schema"] == X_SEARCH_RESPONSE_SCHEMA
    assert "Allowed X handles: @NickTimiraos" in str(payload["input"])
    assert "Prioritize recall" in str(payload["input"])
    assert "model" not in payload
    assert "plugins" not in payload
    assert "x_search_filter" not in payload
    assert "reasoning" not in payload


def test_build_gateway_request_rejects_handle_outside_watchlist() -> None:
    with pytest.raises(ValueError, match="not in the DailyDash X watchlist"):
        build_gateway_request(
            alias="x-retrieve",
            prompt=_prompt(),
            handle="KimDotcom",
            from_date=date(2026, 8, 28),
            to_date=date(2026, 8, 29),
        )


def test_build_gateway_request_rejects_reversed_dates() -> None:
    with pytest.raises(ValueError, match="to_date"):
        build_gateway_request(
            alias="x-retrieve",
            prompt=_prompt(),
            handle="elerianm",
            from_date=date(2026, 8, 29),
            to_date=date(2026, 8, 28),
        )


def test_default_date_range_uses_berlin_calendar_date() -> None:
    now = datetime(2026, 8, 29, 0, 30, tzinfo=ZoneInfo("Europe/Berlin"))
    assert default_date_range(now) == (date(2026, 8, 28), date(2026, 8, 29))


def test_artifact_records_gateway_trace_without_secret_or_upstream_request() -> None:
    prompt = _prompt()
    gateway_request = build_gateway_request(
        alias="x-retrieve",
        prompt=prompt,
        handle="DeItaone",
        from_date=date(2026, 8, 28),
        to_date=date(2026, 8, 29),
    )
    response = GatewayResponse(
        alias="x-retrieve",
        provider="openrouter",
        model="x-ai/grok-4.3",
        generation_id="gen-test",
        content={"posts": []},
        usage=GatewayUsage(
            input_tokens=10,
            output_tokens=4,
            total_tokens=14,
            cost_usd=0.01,
        ),
        latency_ms=321,
        provider_metadata={"server_tool_use": {"web_search": 1}},
    )

    artifact = build_artifact(
        alias="x-retrieve",
        handle="DeItaone",
        from_date=date(2026, 8, 28),
        to_date=date(2026, 8, 29),
        prompt=prompt,
        gateway_request=gateway_request,
        gateway_response=response,
    )

    request_artifact = artifact["request"]
    assert isinstance(request_artifact, dict)
    assert request_artifact["gateway_alias"] == "x-retrieve"
    assert "model" not in request_artifact["payload"]

    response_artifact = artifact["response"]
    assert isinstance(response_artifact, dict)
    assert response_artifact["generation_id"] == "gen-test"
    assert response_artifact["content"] == {"posts": []}
    assert response_artifact["provider_metadata"] == {"server_tool_use": {"web_search": 1}}

    serialized = str(artifact)
    assert "OPENROUTER_API_KEY" not in serialized
    assert "Authorization" not in serialized
