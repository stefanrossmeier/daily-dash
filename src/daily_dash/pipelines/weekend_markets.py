from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from daily_dash.config import WeekendMarketSourceSet, WeekendMarketsProfile
from daily_dash.contracts import WeekendMarketSnapshotDocument
from daily_dash.processing.weekend_markets import process_weekend_market_snapshot
from daily_dash.retrieval.weekend_markets import WeekendMarketRetriever
from daily_dash.storage import WeekendMarketSnapshotStore


def run_weekend_markets_pipeline(
    profile: WeekendMarketsProfile,
    source_set: WeekendMarketSourceSet,
    retriever: WeekendMarketRetriever,
    *,
    snapshot_store: WeekendMarketSnapshotStore,
    run_id: str | None = None,
    now: datetime | None = None,
) -> tuple[WeekendMarketSnapshotDocument, Path]:
    effective_run_id = run_id or str(uuid4())
    effective_now = now or datetime.now(UTC)
    raw = retriever.retrieve(
        source_set,
        run_id=effective_run_id,
        retrieved_at=effective_now,
    )
    if not raw.quotes or all(
        quote.bid is None and quote.ask is None and quote.change_pct is None for quote in raw.quotes
    ):
        raise RuntimeError("all weekend market quotes are unavailable")

    report = process_weekend_market_snapshot(raw, profile_id=profile.profile_id)
    document = WeekendMarketSnapshotDocument(raw=raw, report=report)
    output_path = snapshot_store.save(document)
    return document, output_path
