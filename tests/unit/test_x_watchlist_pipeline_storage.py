from datetime import UTC, datetime
from pathlib import Path

import pytest

from daily_dash.contracts.news import NewsModelUsage
from daily_dash.contracts.x_watchlist import (
    XWatchlistModelEvaluation,
    XWatchlistModelTrace,
    XWatchlistPost,
    XWatchlistRetrievalDiagnostic,
)
from daily_dash.pipelines.x_watchlist import run_x_watchlist_pipeline
from daily_dash.storage.x_watchlist import JsonXWatchlistRunStore

ROOT = Path(__file__).resolve().parents[2]


def _trace(*, search: bool) -> XWatchlistModelTrace:
    return XWatchlistModelTrace(
        prompt_id="x-watchlist-retrieval" if search else "x-watchlist-ranking",
        prompt_version="v3",
        prompt_profile="x-watchlist",
        system_sha256="a" * 64,
        profile_sha256="b" * 64,
        combined_sha256="c" * 64,
        model_alias="x-retrieve" if search else "rank-cheap",
        provider="fixture",
        resolved_model="fixture/model",
        usage=NewsModelUsage(
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            cost_usd=0.001,
        ),
        latency_ms=10,
        attempts=1,
        x_search_call_count=1 if search else 0,
        x_search_queries=["from:NickTimiraos"] if search else [],
        citation_urls=["https://x.com/i/status/123"] if search else [],
    )


class FakeClassifier:
    def __init__(self, client: object) -> None:
        self.client = client

    def classify_batch(self, posts: list[XWatchlistPost], profile: object):
        assert [post.id for post in posts] == ["123"]
        return (
            [
                XWatchlistModelEvaluation(
                    id="123",
                    relevance=90,
                    market_impact=80,
                    market_breadth=70,
                    information_value=85,
                    category="rates",
                    urgency="high",
                    topic_key="fed-rates",
                    rationale="Useful rates information.",
                )
            ],
            _trace(search=False),
        )


def test_x_watchlist_pipeline_ranks_persists_and_summarizes_models(monkeypatch, tmp_path) -> None:
    post = XWatchlistPost(
        id="123",
        author_handle="NickTimiraos",
        publication_time=datetime(2026, 8, 29, 17, 0, tzinfo=UTC),
        post_text="Fed signal",
        post_url="https://x.com/NickTimiraos/status/123",
    )
    diagnostic = XWatchlistRetrievalDiagnostic(
        ok=True,
        allowed_handles=["NickTimiraos"],
        returned_count=1,
        validated_count=1,
        search_call_count=1,
        citation_count=1,
    )

    def fake_retrieve(*args: object, **kwargs: object):
        return [post], diagnostic, _trace(search=True)

    monkeypatch.setattr(
        "daily_dash.pipelines.x_watchlist.retrieve_x_watchlist_posts",
        fake_retrieve,
    )
    monkeypatch.setattr(
        "daily_dash.pipelines.x_watchlist.GatewayXWatchlistClassifier",
        FakeClassifier,
    )

    document, path = run_x_watchlist_pipeline(
        config_dir=ROOT / "config",
        data_repo=tmp_path,
        retrieved_at=datetime(2026, 8, 29, 18, 20, tzinfo=UTC),
        window_start=datetime(2026, 8, 29, 6, 20, tzinfo=UTC),
        window_end=datetime(2026, 8, 29, 18, 20, tzinfo=UTC),
    )

    assert document.selected_ids == ["123"]
    assert document.model_summary is not None
    assert document.model_summary.calls == 2
    assert document.model_summary.usage.total_tokens == 30
    assert document.model_summary.usage.cost_usd == 0.002
    assert path.parent == tmp_path / "x-watchlist/snapshots"
    assert JsonXWatchlistRunStore.read(path) == document

    with pytest.raises(FileExistsError, match="already exists"):
        JsonXWatchlistRunStore(tmp_path).write(document)


def test_x_watchlist_pipeline_rejects_naive_retrieved_at(tmp_path) -> None:
    with pytest.raises(ValueError, match="retrieved_at must be timezone-aware"):
        run_x_watchlist_pipeline(
            config_dir=ROOT / "config",
            data_repo=tmp_path,
            retrieved_at=datetime(2026, 8, 29, 20, 20),
        )
