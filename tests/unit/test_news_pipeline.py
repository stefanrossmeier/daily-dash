from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from daily_dash.contracts.common import SourceKind
from daily_dash.contracts.news import (
    NewsModelSummary,
    NewsModelUsage,
    NewsRankingContent,
    NewsRankingEvaluation,
    NewsRankingTrace,
    NewsSourceDiagnostic,
)
from daily_dash.contracts.source import SourceItem
from daily_dash.pipelines import news as news_pipeline
from daily_dash.pipelines.news import _model_summary


def _trace(*, cost: float, attempts: int = 1, usage_complete: bool = True) -> NewsRankingTrace:
    return NewsRankingTrace(
        prompt_id="fixture",
        prompt_version="v1",
        prompt_profile="news-top",
        system_sha256="a" * 64,
        profile_sha256="b" * 64,
        combined_sha256="c" * 64,
        model_alias="rank-cheap",
        provider="openrouter",
        resolved_model="openai/gpt-5.4-nano",
        usage=NewsModelUsage(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            cost_usd=cost,
        ),
        latency_ms=100,
        attempts=attempts,
        usage_complete=usage_complete,
    )


def test_model_summary_exposes_one_call_and_gateway_retries() -> None:
    summary = _model_summary([_trace(cost=0.003, attempts=3, usage_complete=False)])

    assert summary.usage.input_tokens == 10
    assert summary.usage.output_tokens == 5
    assert summary.usage.total_tokens == 15
    assert summary.usage.cost_usd == 0.003
    assert summary.latency_ms == 100
    assert summary.calls == 1
    assert summary.attempts == 3
    assert summary.retries == 2
    assert summary.usage_complete is False


def test_model_summary_derives_retries_when_reading_older_artifact() -> None:
    summary = NewsModelSummary.model_validate(
        {
            "usage": {},
            "latency_ms": 100,
            "calls": 1,
            "attempts": 3,
            "usage_complete": False,
        }
    )

    assert summary.retries == 2


def test_pipeline_caps_at_150_uses_one_ranking_stage_and_writes_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    now = datetime(2026, 8, 28, 8, 0, tzinfo=UTC)
    items = [
        SourceItem(
            id=f"item-{index:03d}",
            source="Fixture",
            source_kind=SourceKind.RSS,
            title=f"Headline {index:03d}",
            text="fixture",
            url=f"https://example.test/{index}",
            published_at=now - timedelta(minutes=index),
            retrieved_at=now,
            metadata={"source_id": "fixture"},
        )
        for index in range(151)
    ]
    diagnostics = [
        NewsSourceDiagnostic(
            source_id="fixture",
            source_name="Fixture",
            url="https://example.test/feed",
            ok=True,
            item_count=len(items),
        )
    ]

    class FakeRanker:
        calls = 0
        batch_size = 0

        def __init__(self, client: object) -> None:
            del client

        def rank(self, batch: Any, profile: Any) -> tuple[NewsRankingContent, NewsRankingTrace]:
            del profile
            FakeRanker.calls += 1
            FakeRanker.batch_size = len(batch.items)
            evaluations = [
                NewsRankingEvaluation(
                    id=item.id,
                    event_key=f"event-{item.id}",
                    rank_score=80,
                    tier=4,
                    priority=80,
                    relevance=80,
                    market_impact=70,
                    market_breadth=70,
                    surprise=60,
                    quality=80,
                    novelty=70,
                    selected=True,
                    rationale="Fixture.",
                )
                for item in batch.items
            ]
            return (
                NewsRankingContent(
                    evaluations=evaluations,
                    ranking=[item.id for item in batch.items],
                ),
                _trace(cost=0.001),
            )

    monkeypatch.setattr(
        news_pipeline,
        "retrieve_source_set",
        lambda *args, **kwargs: (items, diagnostics),
    )
    monkeypatch.setattr(news_pipeline, "GatewayNewsRanker", FakeRanker)

    data_repo = tmp_path / "data"
    document, artifact = news_pipeline.run_news_pipeline(
        profile_id="news-alternative",
        config_dir=Path(__file__).parents[2] / "config",
        data_repo=data_repo,
        retrieved_at=now,
        window_start=now - timedelta(hours=18),
        window_end=now,
    )

    assert FakeRanker.calls == 1
    assert FakeRanker.batch_size == 150
    assert document.retrieved_count == 151
    assert len(document.retrieved_items) == 151
    assert document.retrieved_items == items
    assert document.candidate_count == 150
    assert document.finalist_count == 150
    assert document.screening is None
    assert document.screening_traces == []
    assert document.model_summary is not None
    assert document.model_summary.calls == 1
    assert document.model_summary.retries == 0
    assert artifact.exists()
