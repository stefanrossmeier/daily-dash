from datetime import UTC, datetime
from pathlib import Path

from daily_dash.config.loader import load_news_profile
from daily_dash.contracts.common import SourceKind
from daily_dash.contracts.news import (
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
    )
    profile = load_news_profile(_REPO_ROOT / "config" / "profiles" / "news-top.yaml")

    artifact = render_news_report(document, profile)

    assert "https://publisher.example/story?id=123&amp;from=rss" in artifact.content
    assert "Rates &amp; markets &lt;move&gt;" in artifact.content
    assert "Publisher &amp; Co" in artifact.content
    assert artifact.metadata["link_provenance"] == "source_item_url"
    assert artifact.metadata["parse_mode"] == "HTML"
