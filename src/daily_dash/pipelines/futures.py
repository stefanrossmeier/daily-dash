from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from daily_dash.config import FuturesProfile, FuturesSourceSet
from daily_dash.contracts.futures import FuturesSnapshotDocument
from daily_dash.processing.futures import process_futures_snapshot
from daily_dash.retrieval.futures import FuturesRetriever
from daily_dash.storage.futures import FuturesSnapshotStore


def run_futures_pipeline(
    profile: FuturesProfile,
    source_set: FuturesSourceSet,
    retriever: FuturesRetriever,
    *,
    snapshot_store: FuturesSnapshotStore,
    run_id: str | None = None,
    now: datetime | None = None,
) -> tuple[FuturesSnapshotDocument, Path]:
    """Run deterministic retrieval/processing and persist before any delivery."""
    effective_run_id = run_id or str(uuid4())
    effective_now = now or datetime.now(UTC)
    raw = retriever.retrieve(source_set, run_id=effective_run_id, retrieved_at=effective_now)
    report = process_futures_snapshot(raw, profile)
    document = FuturesSnapshotDocument(raw=raw, report=report)
    output_path = snapshot_store.save(document)
    return document, output_path
