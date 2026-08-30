from datetime import UTC, datetime
from pathlib import Path

from daily_dash.contracts.news import (
    NewsModelUsage,
    NewsRankingContent,
    NewsRankingEvaluation,
    NewsRankingTrace,
    NewsRunDocument,
)
from daily_dash.storage.news import JsonNewsRunStore


def test_news_store_uses_flat_profile_directory(tmp_path: Path) -> None:
    document = NewsRunDocument(
        run_id="abcdefgh12345678",
        profile="news-top",
        retrieved_at=datetime(2026, 8, 27, 10, 0, tzinfo=UTC),
        source_diagnostics=[],
        retrieved_count=0,
        deduplicated_count=0,
        candidate_count=0,
        candidates=[],
        ranking=NewsRankingContent(
            evaluations=[
                NewsRankingEvaluation(
                    id="one",
                    tier=5,
                    relevance=100,
                    market_impact=100,
                    surprise=90,
                    quality=90,
                    novelty=80,
                    selected=True,
                    rationale="Important.",
                )
            ],
            ranking=["one"],
        ),
        ranking_trace=NewsRankingTrace(
            prompt_id="news-ranking",
            prompt_version="v1",
            prompt_profile="news-top",
            system_sha256="a" * 64,
            profile_sha256="b" * 64,
            combined_sha256="c" * 64,
            model_alias="rank-cheap",
            provider="openrouter",
            resolved_model="test/model",
            usage=NewsModelUsage(),
            latency_ms=1,
        ),
        selected_ids=["one"],
        backfill_ids=["one"],
    )

    output = JsonNewsRunStore(tmp_path).write(document)
    assert output == (tmp_path / "news" / "top" / "20260827T100000Z_abcdefgh.json")
    assert output.is_file()
    assert JsonNewsRunStore.read(output).backfill_ids == ["one"]


def test_news_store_reads_persisted_document(tmp_path: Path) -> None:
    output = JsonNewsRunStore(tmp_path).write(
        NewsRunDocument(
            run_id="readtest12345678",
            profile="news-top",
            retrieved_at=datetime(2026, 8, 27, 10, 0, tzinfo=UTC),
            source_diagnostics=[],
            retrieved_count=0,
            deduplicated_count=0,
            candidate_count=0,
            candidates=[],
            ranking=NewsRankingContent(evaluations=[], ranking=[]),
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
            selected_ids=[],
        )
    )

    loaded = JsonNewsRunStore.read(output)
    assert loaded.run_id == "readtest12345678"
    assert loaded.profile == "news-top"
