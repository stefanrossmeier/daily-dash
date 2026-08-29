from datetime import UTC, datetime

from daily_dash.contracts.polymarket import (
    PolymarketCandidateAudit,
    PolymarketEvaluation,
    PolymarketEventSnapshot,
    PolymarketHotSelection,
    PolymarketRetrievalDiagnostic,
    PolymarketRunDocument,
    PolymarketSignalSelection,
)
from daily_dash.presentation.polymarket import render_polymarket_report
from daily_dash.storage.polymarket import JsonPolymarketRunStore


def _snapshot(event_id: str, title: str, *, volume: float = 1_200_000) -> PolymarketEventSnapshot:
    return PolymarketEventSnapshot(
        id=event_id,
        event_id=101 if event_id == "fed" else 102,
        title=title,
        url=f"https://polymarket.test/{event_id}",
        slug=event_id,
        tags=["finance"],
        volume_24h=volume,
        liquidity=500_000,
        comment_count=80,
        recent_trades=120,
        max_abs_one_hour_price_change=0.05,
        representative_question="Will there be no change?",
        representative_outcome="Yes",
        representative_probability=0.6,
    )


def test_polymarket_compact_artifact_round_trip_and_two_section_report(tmp_path) -> None:
    now = datetime(2026, 8, 29, 18, 45, tzinfo=UTC)
    evaluation = PolymarketEvaluation(
        id="fed",
        relevance=90,
        market_impact=85,
        market_breadth=80,
        prediction_signal=90,
        ranking_score=88,
        topic_key="fed-september-2026-rate-decision",
        theme="monetary-policy",
        signal_type="both",
        rationale="Rates matter broadly.",
        event_slug="fed",
        selection_score=0.88,
        market_eligible=True,
        eligible=True,
    )
    audit = PolymarketCandidateAudit(
        id="fed",
        title="Fed decision in September",
        ranking_score=88,
        relevance=90,
        market_impact=85,
        market_breadth=80,
        prediction_signal=90,
        topic_key="fed-september-2026-rate-decision",
        theme="monetary-policy",
        signal_type="both",
        market_eligible=True,
    )
    document = PolymarketRunDocument(
        run_id="run-poly",
        retrieved_at=now,
        timezone="Europe/Berlin",
        window_start=now,
        window_end=now,
        retrieval_diagnostics=[
            PolymarketRetrievalDiagnostic(
                events_ok=True,
                trades_ok=True,
                semantic_tag_requests=8,
                semantic_event_count=40,
                global_event_count=100,
                unique_event_count=130,
                trade_scope_event_count=30,
                trade_count=120,
                trade_pages=1,
                trade_window_minutes=120,
                trade_window_complete=True,
            )
        ],
        retrieved_count=130,
        candidate_count=1,
        hot_candidate_count=1,
        signals=[
            PolymarketSignalSelection(
                event=_snapshot("fed", "Fed decision in September"),
                evaluation=evaluation,
            )
        ],
        hot=[
            PolymarketHotSelection(
                event=_snapshot("lol", "T1 vs BNK FEARX", volume=2_000_000),
                activity_score=0.91,
            )
        ],
        candidate_audit=[audit],
    )

    path = JsonPolymarketRunStore(tmp_path).write(document)
    restored = JsonPolymarketRunStore.read(path)
    report = render_polymarket_report(restored)

    assert path.parent == tmp_path / "polymarket/snapshots"
    assert restored.schema_version == 2
    assert "Market Signals" in report.content
    assert "Fed decision in September" in report.content
    assert "Hot on Polymarket" in report.content
    assert "T1 vs BNK FEARX" in report.content
    assert "24h Vol $1.2M" in report.content


def test_polymarket_artifact_stays_compact_without_rejected_descriptions(tmp_path) -> None:
    now = datetime(2026, 8, 29, 18, 45, tzinfo=UTC)
    audits = [
        PolymarketCandidateAudit(
            id=f"event-{index}",
            title=f"Candidate event {index} with a reasonably descriptive title",
            ranking_score=70 - index,
            relevance=70,
            market_impact=60,
            market_breadth=60,
            prediction_signal=65,
            topic_key=f"topic-{index}",
            theme="macro-economy",
            signal_type="market-moving-bet",
            market_eligible=index < 7,
        )
        for index in range(30)
    ]
    document = PolymarketRunDocument(
        run_id="compact-run",
        retrieved_at=now,
        timezone="Europe/Berlin",
        window_start=now,
        window_end=now,
        retrieval_diagnostics=[],
        retrieved_count=200,
        candidate_count=30,
        hot_candidate_count=30,
        candidate_audit=audits,
    )

    path = JsonPolymarketRunStore(tmp_path).write(document)

    assert path.stat().st_size < 50_000
