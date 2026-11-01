from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from daily_dash.config import YahooMoversProfile, YahooMoversSourceSet
from daily_dash.contracts import MoversSnapshotDocument
from daily_dash.processing.yahoo_movers import process_movers_snapshot
from daily_dash.retrieval.yahoo_movers import YahooMoversRetriever
from daily_dash.storage import YahooMoversSnapshotStore


def run_yahoo_movers_pipeline(
    profile: YahooMoversProfile,
    source_set: YahooMoversSourceSet,
    retriever: YahooMoversRetriever,
    *,
    snapshot_store: YahooMoversSnapshotStore,
    run_id: str | None = None,
    now: datetime | None = None,
) -> tuple[MoversSnapshotDocument, Path]:
    effective_run_id = run_id or str(uuid4())
    effective_now = now or datetime.now(UTC)
    raw = retriever.retrieve(source_set, run_id=effective_run_id, retrieved_at=effective_now)

    available = [
        category for category in raw.categories if category.movers and category.error is None
    ]
    if not available:
        raise RuntimeError("all Yahoo Movers categories are unavailable")

    report = process_movers_snapshot(raw, source_set, profile)
    if not report.sections:
        raise RuntimeError("no Yahoo Movers sections could be processed")

    document = MoversSnapshotDocument(raw=raw, report=report)
    output_path = snapshot_store.save(document)
    return document, output_path
