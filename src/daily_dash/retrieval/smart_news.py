from __future__ import annotations

import time
from datetime import datetime

import httpx

from daily_dash.config.models import NewsSourceSet
from daily_dash.contracts.news import NewsSourceDiagnostic
from daily_dash.contracts.source import SourceItem
from daily_dash.retrieval.rss import DEFAULT_HEADERS, fetch_source


def retrieve_smart_source_set(
    source_set: NewsSourceSet,
    *,
    max_items_per_source: int,
    lookback_hours: int | None,
    retrieved_at: datetime,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    timeout_seconds: float = 20.0,
    retries: int = 2,
) -> tuple[list[SourceItem], list[NewsSourceDiagnostic]]:
    """Retrieve Smart News feeds with the legacy two-retry policy."""

    if retries < 0:
        raise ValueError("retries must not be negative")

    items: list[SourceItem] = []
    diagnostics: list[NewsSourceDiagnostic] = []

    with httpx.Client(
        timeout=timeout_seconds,
        headers=DEFAULT_HEADERS,
        follow_redirects=True,
    ) as client:
        for source in source_set.sources:
            if not source.enabled:
                continue

            source_items: list[SourceItem] = []
            diagnostic: NewsSourceDiagnostic | None = None

            for attempt in range(retries + 1):
                source_items, diagnostic = fetch_source(
                    client,
                    source=source,
                    retrieved_at=retrieved_at,
                    max_items=max_items_per_source,
                    lookback_hours=lookback_hours,
                    window_start=window_start,
                    window_end=window_end,
                )
                if diagnostic.ok:
                    break
                if attempt < retries:
                    time.sleep(0.6 * (attempt + 1))

            if diagnostic is None:
                raise RuntimeError(f"no retrieval diagnostic produced for {source.id}")

            items.extend(source_items)
            diagnostics.append(diagnostic)

    return items, diagnostics
