from datetime import UTC, datetime
from pathlib import Path

import pytest

from daily_dash.config.loader import load_x_watchlist_profile
from daily_dash.contracts.x_watchlist import XWatchlistPost
from daily_dash.llm.gateway import GatewayResponse, GatewayUsage
from daily_dash.llm.x_watchlist import GatewayXWatchlistClassifier

ROOT = Path(__file__).resolve().parents[2]


class FakeClient:
    def __init__(self, content: dict[str, object]) -> None:
        self.content = content
        self.request: dict[str, object] | None = None

    def chat_structured(self, **kwargs: object) -> GatewayResponse:
        self.request = kwargs
        return GatewayResponse(
            alias="rank-cheap",
            provider="openrouter",
            model="openai/gpt-5.4-nano",
            generation_id="x-rank-test",
            content=self.content,
            usage=GatewayUsage(
                input_tokens=25,
                output_tokens=15,
                total_tokens=40,
                cost_usd=0.0002,
            ),
            latency_ms=200,
            attempts=1,
        )


def _post() -> XWatchlistPost:
    return XWatchlistPost(
        id="123",
        author_handle="NickTimiraos",
        publication_time=datetime(2026, 8, 29, 17, 0, tzinfo=UTC),
        post_text="Treasury yields moved sharply after the Fed speech.",
        post_url="https://x.com/NickTimiraos/status/123",
    )


def test_x_watchlist_classifier_uses_versioned_prompt_and_structured_slots() -> None:
    profile = load_x_watchlist_profile(ROOT / "config/profiles/x-watchlist.yaml")
    client = FakeClient(
        {
            "evaluations": {
                "X001": {
                    "relevance": 90,
                    "market_impact": 80,
                    "market_breadth": 70,
                    "information_value": 85,
                    "category": "rates",
                    "urgency": "high",
                    "topic_key": "fed-rates",
                    "rationale": "Useful rates information.",
                }
            }
        }
    )

    evaluations, trace = GatewayXWatchlistClassifier(client).classify_batch([_post()], profile)

    assert evaluations[0].id == "123"
    assert evaluations[0].category == "rates"
    assert trace.prompt_id == "x-watchlist-ranking"
    assert trace.prompt_version == "v4"
    assert trace.resolved_model == "openai/gpt-5.4-nano"
    assert client.request is not None
    assert client.request["alias"] == "rank-cheap"
    user = str(client.request["user"])
    assert "NickTimiraos" in user
    assert "Treasury yields moved sharply" in user
    assert "popularity" in user


def test_x_watchlist_classifier_rejects_missing_evaluations_object() -> None:
    profile = load_x_watchlist_profile(ROOT / "config/profiles/x-watchlist.yaml")
    client = FakeClient({"unexpected": {}})

    with pytest.raises(ValueError, match="evaluations must be an object"):
        GatewayXWatchlistClassifier(client).classify_batch([_post()], profile)


def test_x_watchlist_classifier_rejects_missing_slot() -> None:
    profile = load_x_watchlist_profile(ROOT / "config/profiles/x-watchlist.yaml")
    client = FakeClient({"evaluations": {}})

    with pytest.raises(ValueError, match="missing X Watchlist evaluation for slot X001"):
        GatewayXWatchlistClassifier(client).classify_batch([_post()], profile)
