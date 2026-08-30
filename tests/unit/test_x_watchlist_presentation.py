from datetime import UTC, datetime
from pathlib import Path

from daily_dash.config.loader import load_x_watchlist_profile
from daily_dash.contracts.x_watchlist import (
    XWatchlistEvaluation,
    XWatchlistPost,
    XWatchlistRetrievalDiagnostic,
    XWatchlistRunDocument,
)
from daily_dash.presentation.x_watchlist import render_x_watchlist_report

ROOT = Path(__file__).resolve().parents[2]


def _profile():
    return load_x_watchlist_profile(ROOT / "config/profiles/x-watchlist.yaml")


def test_report_preserves_original_post_and_x_url() -> None:
    post = XWatchlistPost(
        id="123",
        author_handle="NickTimiraos",
        publication_time=datetime(2026, 8, 28, 18, 0, tzinfo=UTC),
        post_text="Original <market> post",
        post_url="https://x.com/NickTimiraos/status/123",
    )
    evaluation = XWatchlistEvaluation(
        id="123",
        relevance=90,
        market_impact=80,
        market_breadth=70,
        information_value=95,
        category="monetary-policy",
        urgency="high",
        topic_key="fed-policy",
        rationale="Direct Fed policy information.",
        semantic_score=0.85,
        eligible=True,
    )
    doc = XWatchlistRunDocument(
        run_id="run",
        retrieved_at=datetime(2026, 8, 28, 20, 20, tzinfo=UTC),
        window_start=datetime(2026, 8, 28, 8, 20, tzinfo=UTC),
        window_end=datetime(2026, 8, 28, 20, 20, tzinfo=UTC),
        timezone="Europe/Berlin",
        retrieval_diagnostic=XWatchlistRetrievalDiagnostic(
            ok=True,
            allowed_handles=["NickTimiraos"],
            returned_count=1,
            validated_count=1,
        ),
        retrieved_count=1,
        candidate_count=1,
        candidates=[post],
        evaluations=[evaluation],
        selected_ids=["123"],
    )
    report = render_x_watchlist_report(doc, _profile())
    assert "@NickTimiraos" in report.content
    assert "Original &lt;market&gt; post" in report.content
    assert "https://x.com/NickTimiraos/status/123" in report.content
    assert "Direct Fed policy information." not in report.content
    assert "Signal" not in report.content
    assert "Impact" not in report.content
    assert "Info" not in report.content
    assert "monetary-policy" not in report.content


def test_report_does_not_clip_selected_post_text() -> None:
    text = "x" * 1800
    post = XWatchlistPost(
        id="456",
        author_handle="KobeissiLetter",
        publication_time=datetime(2026, 8, 28, 18, 0, tzinfo=UTC),
        post_text=text,
        post_url="https://x.com/KobeissiLetter/status/456",
    )
    evaluation = XWatchlistEvaluation(
        id="456",
        relevance=90,
        market_impact=80,
        market_breadth=70,
        information_value=95,
        category="macro",
        urgency="high",
        topic_key="macro-event",
        rationale="Internal rationale must stay out of Telegram.",
        semantic_score=0.85,
        eligible=True,
    )
    doc = XWatchlistRunDocument(
        run_id="run-long",
        retrieved_at=datetime(2026, 8, 28, 20, 20, tzinfo=UTC),
        window_start=datetime(2026, 8, 28, 8, 20, tzinfo=UTC),
        window_end=datetime(2026, 8, 28, 20, 20, tzinfo=UTC),
        timezone="Europe/Berlin",
        retrieval_diagnostic=XWatchlistRetrievalDiagnostic(
            ok=True, allowed_handles=["KobeissiLetter"], returned_count=1, validated_count=1
        ),
        retrieved_count=1,
        candidate_count=1,
        candidates=[post],
        evaluations=[evaluation],
        selected_ids=["456"],
    )
    report = render_x_watchlist_report(doc, _profile())
    assert text in report.content
    assert "Internal rationale" not in report.content


def test_empty_x_watchlist_uses_plain_user_facing_message() -> None:
    doc = XWatchlistRunDocument(
        run_id="empty-x",
        retrieved_at=datetime(2026, 8, 29, 20, 20, tzinfo=UTC),
        window_start=datetime(2026, 8, 29, 8, 20, tzinfo=UTC),
        window_end=datetime(2026, 8, 29, 20, 20, tzinfo=UTC),
        timezone="Europe/Berlin",
        retrieval_diagnostic=XWatchlistRetrievalDiagnostic(
            ok=True,
            allowed_handles=["NickTimiraos"],
            returned_count=0,
            validated_count=0,
        ),
        retrieved_count=0,
        candidate_count=0,
        candidates=[],
        evaluations=[],
        selected_ids=[],
    )

    report = render_x_watchlist_report(doc, _profile())

    assert "No relevant X posts were found in this report window." in report.content
    assert "selected" not in report.content.lower()
