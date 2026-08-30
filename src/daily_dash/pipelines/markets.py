from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from daily_dash.config import MarketSourceSet, MarketsProfile
from daily_dash.contracts.market import MarketSnapshotDocument
from daily_dash.processing.markets import process_market_snapshot
from daily_dash.retrieval.markets import MarketRetriever
from daily_dash.storage import MarketSnapshotStore


def _build_market_snapshot(
    profile: MarketsProfile,
    source_set: MarketSourceSet,
    retriever: MarketRetriever,
    *,
    run_id: str | None = None,
    now: datetime | None = None,
) -> MarketSnapshotDocument:
    effective_run_id = run_id or str(uuid4())
    effective_now = now or datetime.now(UTC)

    raw = retriever.retrieve(
        source_set,
        run_id=effective_run_id,
        retrieved_at=effective_now,
    )
    processed = process_market_snapshot(raw, profile_id=profile.profile_id)

    return MarketSnapshotDocument(
        raw=raw,
        report=processed,
    )


def run_markets_pipeline(
    profile: MarketsProfile,
    source_set: MarketSourceSet,
    retriever: MarketRetriever,
    *,
    snapshot_store: MarketSnapshotStore,
    run_id: str | None = None,
    now: datetime | None = None,
) -> tuple[MarketSnapshotDocument, Path]:
    """Run Markets and persist its immutable output artifact before delivery."""
    document = _build_market_snapshot(
        profile,
        source_set,
        retriever,
        run_id=run_id,
        now=now,
    )
    output_path = snapshot_store.save(document)
    return document, output_path
