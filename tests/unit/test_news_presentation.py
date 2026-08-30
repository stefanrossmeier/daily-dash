from datetime import UTC, datetime
from pathlib import Path

import pytest

from daily_dash.config.loader import load_news_profile
from daily_dash.contracts.common import SourceKind
from daily_dash.contracts.news import (
    NewsDuplicateSuppression,
    NewsModelUsage,
    NewsRankingContent,
    NewsRankingEvaluation,
    NewsRankingTrace,
    NewsRunDocument,
)
from daily_dash.contracts.source import SourceItem
from daily_dash.presentation.news import render_news_report

_REPO_ROOT = Path(__file__).parents[2]


def test_news_report_links_to_original_source_item_url() -> None:
    now = datetime(2026, 8, 27, 10, 0, tzinfo=UTC)
    original_url = "https://publisher.example/story?id=123&from=rss"
    item = SourceItem(
        id="story-1",
        source="Publisher & Co",
        source_kind=SourceKind.RSS,
        title="Rates & markets <move>",
        text="Summary",
        url=original_url,
        published_at=now,
        retrieved_at=now,
        metadata={"source_id": "publisher"},
    )
    evaluation = NewsRankingEvaluation(
        id=item.id,
        event_key="rates-market-move",
        rank_score=95,
        tier=5,
        priority=95,
        relevance=100,
        market_impact=95,
        surprise=90,
        quality=90,
        novelty=80,
        selected=True,
        rationale="Important.",
    )
    document = NewsRunDocument(
        run_id="run-1",
        profile="news-top",
        retrieved_at=now,
        source_diagnostics=[],
        retrieved_count=1,
        deduplicated_count=1,
        candidate_count=1,
        candidates=[item],
        ranking=NewsRankingContent(evaluations=[evaluation], ranking=[item.id]),
        ranking_trace=NewsRankingTrace(
            prompt_id="news-ranking",
            prompt_version="v3",
            prompt_profile="news-top",
            system_sha256="a" * 64,
            profile_sha256="b" * 64,
            combined_sha256="c" * 64,
            model_alias="rank-cheap",
            provider="fixture",
            resolved_model="fixture/model",
            usage=NewsModelUsage(),
            latency_ms=1,
        ),
        selected_ids=[item.id],
        duplicate_suppressions=[
            NewsDuplicateSuppression(
                suppressed_id="story-duplicate",
                kept_id=item.id,
                event_key="rates-market-move",
            )
        ],
    )
    profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / "news-top.yaml")

    artifact = render_news_report(document, profile)

    assert "https://publisher.example/story?id=123&amp;from=rss" in artifact.content
    assert "Rates &amp; markets &lt;move&gt;" in artifact.content
    assert "Publisher &amp; Co" in artifact.content
    assert artifact.metadata["link_provenance"] == "source_item_url"
    assert artifact.metadata["parse_mode"] == "HTML"
    assert "duplicate article" not in artifact.content
    assert "suppressed" not in artifact.content


def _empty_news_document(profile: str) -> NewsRunDocument:
    now = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    return NewsRunDocument(
        run_id=f"empty-{profile}",
        profile=profile,
        retrieved_at=now,
        source_diagnostics=[],
        retrieved_count=0,
        deduplicated_count=0,
        candidate_count=0,
        candidates=[],
        ranking=NewsRankingContent(evaluations=[], ranking=[]),
        ranking_trace=NewsRankingTrace(
            prompt_id="news-ranking",
            prompt_version="v10",
            prompt_profile=profile,
            system_sha256="a" * 64,
            profile_sha256="b" * 64,
            combined_sha256="c" * 64,
            model_alias="rank-cheap",
            provider="fixture",
            resolved_model="fixture/model",
            usage=NewsModelUsage(),
            latency_ms=1,
        ),
        selected_ids=[],
    )


def test_alternative_news_empty_report_explains_the_window() -> None:
    profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / "news-alternative.yaml")
    artifact = render_news_report(_empty_news_document("news-alternative"), profile)

    assert "Alternative News" in artifact.content
    assert "No relevant new articles were found in this report window." in artifact.content


def test_german_news_empty_report_uses_english_empty_state() -> None:
    profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / "news-german.yaml")
    artifact = render_news_report(_empty_news_document("news-german"), profile)

    assert "German News" in artifact.content
    assert "No relevant new articles were found in this report window." in artifact.content
    assert "Im Berichtszeitraum" not in artifact.content


def test_news_report_can_render_selected_item_without_url() -> None:
    now = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    item = SourceItem(
        id="story-no-url",
        source="Wire",
        source_kind=SourceKind.RSS,
        title="Headline without URL",
        text="",
        published_at=now,
        retrieved_at=now,
    )
    evaluation = NewsRankingEvaluation(
        id=item.id,
        event_key="headline-no-url",
        rank_score=60,
        tier=3,
        priority=60,
        relevance=60,
        market_impact=50,
        surprise=40,
        quality=50,
        novelty=50,
        selected=True,
        rationale="Useful.",
    )
    document = _empty_news_document("news-top").model_copy(
        update={
            "retrieved_count": 1,
            "deduplicated_count": 1,
            "candidate_count": 1,
            "candidates": [item],
            "ranking": NewsRankingContent(evaluations=[evaluation], ranking=[item.id]),
            "selected_ids": [item.id],
        }
    )
    profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / "news-top.yaml")

    artifact = render_news_report(document, profile)

    assert "Headline without URL" in artifact.content
    assert "href=" not in artifact.content


def test_news_report_rejects_selected_id_missing_from_candidates() -> None:
    profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / "news-top.yaml")
    document = _empty_news_document("news-top").model_copy(update={"selected_ids": ["missing"]})

    with pytest.raises(ValueError, match="selected news item is missing"):
        render_news_report(document, profile)


def test_news_report_marks_where_backfill_headlines_begin() -> None:
    now = datetime(2026, 8, 30, 10, 0, tzinfo=UTC)
    items = [
        SourceItem(
            id=item_id,
            source="Wire",
            source_kind=SourceKind.RSS,
            title=title,
            text="",
            url=f"https://example.test/{item_id}",
            published_at=now,
            retrieved_at=now,
        )
        for item_id, title in [("primary", "Primary headline"), ("fallback", "Fallback headline")]
    ]
    evaluations = [
        NewsRankingEvaluation(
            id=item.id,
            event_key=item.id,
            rank_score=90 if item.id == "primary" else 80,
            tier=4,
            priority=80,
            relevance=80,
            market_impact=70,
            surprise=60,
            quality=80,
            novelty=70,
            selected=item.id == "primary",
            rationale="Fixture.",
        )
        for item in items
    ]
    document = _empty_news_document("news-top").model_copy(
        update={
            "retrieved_count": 2,
            "deduplicated_count": 2,
            "candidate_count": 2,
            "candidates": items,
            "ranking": NewsRankingContent(
                evaluations=evaluations,
                ranking=["primary", "fallback"],
            ),
            "selected_ids": ["primary", "fallback"],
            "backfill_ids": ["fallback"],
        }
    )
    profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / "news-top.yaml")

    artifact = render_news_report(document, profile)

    assert artifact.content.index("Primary headline") < artifact.content.index("<i>Backfill:</i>")
    assert artifact.content.index("<i>Backfill:</i>") < artifact.content.index("Fallback headline")
    assert artifact.metadata["backfill_count"] == 1
