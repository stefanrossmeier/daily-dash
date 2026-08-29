from datetime import UTC, datetime

from daily_dash.contracts.wsb import (
    WsbEvaluation,
    WsbPost,
    WsbRetrievalDiagnostic,
    WsbRunDocument,
)
from daily_dash.presentation.wsb import render_wsb_report
from daily_dash.storage.wsb import JsonWsbRunStore


def _document() -> WsbRunDocument:
    now = datetime(2026, 8, 28, 18, 35, tzinfo=UTC)
    post = WsbPost(
        id="macro",
        title="Rates shock & broad repricing",
        text="",
        url="https://reddit.test/macro",
        created_at=now,
        num_comments=123,
        score=456,
        heat=10.0,
    )
    evaluation = WsbEvaluation(
        id="macro",
        relevance=90,
        market_impact=85,
        market_breadth=80,
        positioning_signal=20,
        signal_type="broad-market",
        rationale="Rates transmit through index valuation and funding conditions.",
        semantic_score=0.82,
        activity_score=0.5,
        selection_score=0.77,
        market_eligible=True,
        extreme_activity_eligible=False,
        eligible=True,
    )
    return WsbRunDocument(
        run_id="run-wsb",
        retrieved_at=now,
        window_start=now,
        timezone="Europe/Berlin",
        window_end=now,
        retrieval_diagnostics=[WsbRetrievalDiagnostic(mode="public-json", ok=True, item_count=1)],
        retrieved_count=1,
        candidate_count=1,
        candidates=[post],
        evaluations=[evaluation],
        selected_ids=["macro"],
    )


def test_wsb_artifact_round_trip_and_report(tmp_path) -> None:
    document = _document()
    path = JsonWsbRunStore(tmp_path).write(document)
    restored = JsonWsbRunStore.read(path)
    report = render_wsb_report(restored)

    assert path.parent == tmp_path / "wsb/snapshots"
    assert restored.selected_ids == ["macro"]
    assert "Signals & Hot Topics" in report.content
    assert "Rates shock &amp; broad repricing" in report.content
    assert "Broad market" in report.content
    assert "Signal 0.77" in report.content
    assert "123 💬" in report.content
