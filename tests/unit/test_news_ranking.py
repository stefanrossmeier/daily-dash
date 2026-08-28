from datetime import UTC, datetime
from pathlib import Path

import pytest

from daily_dash.config.loader import load_news_profile
from daily_dash.contracts.common import SourceKind
from daily_dash.contracts.source import CandidateBatch, SourceItem
from daily_dash.llm.gateway import GatewayResponse, GatewayUsage
from daily_dash.ranking.news import GatewayNewsRanker, _ranking_schema

_REPO_ROOT = Path(__file__).parents[2]


def _candidate(item_id: str, title: str) -> SourceItem:
    now = datetime(2026, 8, 27, 10, 0, tzinfo=UTC)
    return SourceItem(
        id=item_id,
        source="Fixture",
        source_kind=SourceKind.RSS,
        title=title,
        text="fixture",
        url=f"https://publisher.example/{item_id}?original=1",
        published_at=now,
        retrieved_at=now,
        metadata={"source_id": "fixture"},
    )


class FakeGateway:
    def __init__(self) -> None:
        self.user = ""
        self.calls = 0

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
        del purpose, profile, system, response_schema
        self.calls += 1
        self.user = user
        assert response_schema_name == "daily_dash_news_ranking_v10"
        return GatewayResponse(
            alias=alias,
            provider="openrouter",
            model="test/model",
            generation_id="gen-test",
            content={
                "evaluations": {
                    "C001": {
                        "event_key": "fed-emergency-cut",
                        "duplicate_of_slot": "NONE",
                        "rank_score": 72,
                        "tier": 5,
                        "priority": 95,
                        "relevance": 100,
                        "market_impact": 100,
                        "market_breadth": 100,
                        "surprise": 95,
                        "quality": 90,
                        "novelty": 90,
                        "selected": True,
                        "rationale": "Systemic policy shock.",
                    },
                    "C002": {
                        "event_key": "market-plumbing-change",
                        "duplicate_of_slot": "NONE",
                        "rank_score": 91,
                        "tier": 4,
                        "priority": 80,
                        "relevance": 85,
                        "market_impact": 70,
                        "market_breadth": 45,
                        "surprise": 70,
                        "quality": 85,
                        "novelty": 75,
                        "selected": True,
                        "rationale": "The LLM ranks this first overall.",
                    },
                }
            },
            usage=GatewayUsage(
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                cost_usd=0.001,
            ),
            latency_ms=123,
        )


def test_ranker_preserves_raw_llm_rank_score_order_before_top_policy() -> None:
    profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / "news-top.yaml")
    gateway = FakeGateway()

    content, trace = GatewayNewsRanker(gateway).rank(
        CandidateBatch(
            run_id="run-test",
            profile="news-top",
            items=[
                _candidate("one", "Emergency rate cut"),
                _candidate("two", "Market plumbing change"),
            ],
        ),
        profile,
    )

    # GatewayNewsRanker preserves the raw LLM ordering. The Top pipeline
    # applies its deterministic market policy after this ranking step.
    assert content.ranking == ["two", "one"]
    assert trace.prompt_version == "v10"
    assert gateway.calls == 1
    assert trace.attempts == 1


def test_model_input_excludes_original_article_urls() -> None:
    profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / "news-top.yaml")
    gateway = FakeGateway()

    GatewayNewsRanker(gateway).rank(
        CandidateBatch(
            run_id="url-test",
            profile="news-top",
            items=[
                _candidate("one", "Emergency rate cut"),
                _candidate("two", "Market plumbing change"),
            ],
        ),
        profile,
    )

    assert "publisher.example" not in gateway.user
    assert '"url"' not in gateway.user
    assert '"source"' not in gateway.user
    assert '"summary"' not in gateway.user
    assert '"published_at"' not in gateway.user
    assert '"headline": "Emergency rate cut"' in gateway.user


def test_all_news_profiles_use_v10_with_profile_neutral_selection_instruction() -> None:
    for profile_id in ("news-top", "news-alternative", "news-german"):
        profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / f"{profile_id}.yaml")
        gateway = FakeGateway()

        _, trace = GatewayNewsRanker(gateway).rank(
            CandidateBatch(
                run_id=f"{profile_id}-v10-test",
                profile=profile_id,
                items=[
                    _candidate("one", "Emergency rate cut"),
                    _candidate("two", "Market plumbing change"),
                ],
            ),
            profile,
        )

        assert trace.prompt_version == "v10"
        assert gateway.calls == 1
        assert "this news profile" in gateway.user
        assert "Top-News consideration" not in gateway.user


def test_v6_schema_requires_rank_score_event_key_and_market_breadth() -> None:
    schema = _ranking_schema(["C001"], include_market_breadth=True)
    root = schema["properties"]
    assert isinstance(root, dict)
    evaluations = root["evaluations"]
    assert isinstance(evaluations, dict)
    properties = evaluations["properties"]
    assert isinstance(properties, dict)
    candidate = properties["C001"]
    assert isinstance(candidate, dict)
    required = candidate["required"]
    assert isinstance(required, list)
    assert "event_key" in required
    assert "rank_score" in required
    assert "market_breadth" in required


def test_v6_schema_requires_duplicate_relation() -> None:
    from daily_dash.ranking.news import (
        _evaluation_schema,
    )

    schema = _evaluation_schema(include_market_breadth=True)

    assert "duplicate_of_slot" in schema["properties"]
    assert "duplicate_of_slot" in schema["required"]


def test_v5_schema_remains_reproducible_without_market_breadth() -> None:
    from daily_dash.ranking.news import _evaluation_schema

    schema = _evaluation_schema()

    assert "market_breadth" not in schema["properties"]
    assert "market_breadth" not in schema["required"]


def test_v10_uses_market_breadth_schema_without_new_semantic_fields() -> None:
    schema = _ranking_schema(["C001"], include_market_breadth=True)
    root = schema["properties"]
    assert isinstance(root, dict)
    evaluations = root["evaluations"]
    assert isinstance(evaluations, dict)
    properties = evaluations["properties"]
    assert isinstance(properties, dict)
    candidate = properties["C001"]
    assert isinstance(candidate, dict)
    required = candidate["required"]
    assert isinstance(required, list)
    assert "rank_score" in required
    assert "market_impact" in required
    assert "market_breadth" in required


class InvalidGateway:
    def __init__(self) -> None:
        self.calls = 0

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
        del purpose, profile, system, user, response_schema_name, response_schema
        self.calls += 1
        return GatewayResponse(
            alias=alias,
            provider="openrouter",
            model="test/model",
            content={"evaluations": {}},
            usage=GatewayUsage(),
            latency_ms=1,
        )


class SelfDuplicateGateway(FakeGateway):
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
        response = super().chat_structured(
            alias=alias,
            purpose=purpose,
            profile=profile,
            system=system,
            user=user,
            response_schema_name=response_schema_name,
            response_schema=response_schema,
        )
        evaluations = response.content["evaluations"]
        assert isinstance(evaluations, dict)
        first = evaluations["C001"]
        assert isinstance(first, dict)
        first["duplicate_of_slot"] = "C001"
        return response


def test_ranker_normalizes_self_duplicate_relation_without_retry() -> None:
    profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / "news-top.yaml")
    gateway = SelfDuplicateGateway()

    content, trace = GatewayNewsRanker(gateway).rank(
        CandidateBatch(
            run_id="self-duplicate",
            profile="news-top",
            items=[
                _candidate("one", "Emergency rate cut"),
                _candidate("two", "Market plumbing change"),
            ],
        ),
        profile,
    )

    evaluations = {evaluation.id: evaluation for evaluation in content.evaluations}
    assert evaluations["one"].duplicate_of_id is None
    assert gateway.calls == 1
    assert trace.attempts == 1


def test_ranker_does_not_issue_application_level_repair_call() -> None:
    profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / "news-top.yaml")
    gateway = InvalidGateway()

    with pytest.raises(RuntimeError, match="failed local validation"):
        GatewayNewsRanker(gateway).rank(
            CandidateBatch(
                run_id="invalid-response",
                profile="news-top",
                items=[_candidate("one", "Emergency rate cut")],
            ),
            profile,
        )

    assert gateway.calls == 1
