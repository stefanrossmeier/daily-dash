from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from daily_dash.config import YieldProfile, YieldSourceSet
from daily_dash.contracts import YieldSnapshotDocument
from daily_dash.processing.yields import process_yield_snapshot
from daily_dash.retrieval.yields import YieldRetriever
from daily_dash.storage import YieldSnapshotStore


def run_yield_pipeline(
    profile: YieldProfile,
    source_set: YieldSourceSet,
    retriever: YieldRetriever,
    *,
    snapshot_store: YieldSnapshotStore,
    run_id: str | None = None,
    now: datetime | None = None,
) -> tuple[YieldSnapshotDocument, Path]:
    effective_run_id = run_id or str(uuid4())
    effective_now = now or datetime.now(ZoneInfo(profile.presentation.timezone))
    raw = retriever.retrieve(source_set, run_id=effective_run_id, retrieved_at=effective_now)

    available = [series for series in raw.series if series.observations and series.error is None]
    if not available:
        raise RuntimeError("all Yield Report series are unavailable")

    report = process_yield_snapshot(raw, profile)
    document = YieldSnapshotDocument(raw=raw, report=report)
    output_path = snapshot_store.save(document)
    return document, output_path
