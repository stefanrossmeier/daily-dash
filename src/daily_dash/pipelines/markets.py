from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from daily_dash.config import MarketSourceSet, MarketsProfile
from daily_dash.contracts import ReportArtifact
from daily_dash.contracts.market import MarketSnapshotDocument
from daily_dash.presentation.markets import render_markets_report
from daily_dash.processing.markets import process_market_snapshot
from daily_dash.retrieval.markets import MarketRetriever
from daily_dash.storage import MarketSnapshotStore


def run_markets(
    profile: MarketsProfile,
    source_set: MarketSourceSet,
    retriever: MarketRetriever,
    *,
    run_id: str | None = None,
    now: datetime | None = None,
    snapshot_store: MarketSnapshotStore | None = None,
) -> ReportArtifact:
    effective_run_id = run_id or str(uuid4())
    effective_now = now or datetime.now(ZoneInfo(profile.presentation.timezone))

    raw = retriever.retrieve(
        source_set,
        run_id=effective_run_id,
        retrieved_at=effective_now,
    )
    processed = process_market_snapshot(raw, profile_id=profile.profile_id)

    if snapshot_store is not None:
        snapshot_store.save(
            MarketSnapshotDocument(
                raw=raw,
                report=processed,
            )
        )

    return render_markets_report(processed, profile)
