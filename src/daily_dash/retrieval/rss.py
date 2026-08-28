from __future__ import annotations

import calendar
import hashlib
import html
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import feedparser  # type: ignore[import-untyped]
import httpx
from pydantic import HttpUrl

from daily_dash.config.models import NewsSourceSet, RssSourceConfig
from daily_dash.contracts.common import SourceKind
from daily_dash.contracts.news import NewsSourceDiagnostic
from daily_dash.contracts.source import SourceItem

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")

DEFAULT_HEADERS = {
    "User-Agent": "daily-dash/1.0 (+https://github.com/stefanrossmeier/daily-dash)",
    "Accept": (
        "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.1"
    ),
}


def clean_feed_text(value: object, *, max_length: int = 1200) -> str:
    text = html.unescape(str(value or ""))
    text = _TAG_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()

    if len(text) <= max_length:
        return text

    return text[: max_length - 1].rstrip() + "…"


def _parsed_datetime(entry: Any) -> datetime | None:
    raw = entry.get("published_parsed") or entry.get("updated_parsed")

    if raw is None:
        return None

    try:
        return datetime.fromtimestamp(calendar.timegm(raw), tz=UTC)
    except (OverflowError, TypeError, ValueError):
        return None


def _stable_item_id(source_id: str, link: str, title: str) -> str:
    value = f"{source_id}\n{link}\n{title}".encode()
    return hashlib.sha256(value).hexdigest()[:24]


def parse_feed_bytes(
    data: bytes,
    *,
    source: RssSourceConfig,
    retrieved_at: datetime,
    max_items: int,
    lookback_hours: int | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> list[SourceItem]:
    parsed = feedparser.parse(data)

    if (window_start is None) != (window_end is None):
        raise ValueError("window_start and window_end must be supplied together")

    if window_start is not None and window_end is not None:
        if window_start.tzinfo is None or window_end.tzinfo is None:
            raise ValueError("retrieval window must be timezone-aware")
        start = window_start.astimezone(UTC)
        end = window_end.astimezone(UTC)
        if start >= end:
            raise ValueError("retrieval window start must be before end")
    else:
        if lookback_hours is None:
            raise ValueError("lookback_hours is required when no retrieval window is supplied")
        start = retrieved_at - timedelta(hours=lookback_hours)
        end = retrieved_at + timedelta(microseconds=1)
    items: list[SourceItem] = []

    for entry in parsed.entries[:max_items]:
        title = clean_feed_text(entry.get("title"))
        link = str(entry.get("link") or entry.get("id") or "").strip()

        if not title or not link:
            continue

        published_at = _parsed_datetime(entry)

        if published_at is not None and not (start <= published_at < end):
            continue

        summary = clean_feed_text(entry.get("summary") or entry.get("description") or "")

        items.append(
            SourceItem(
                id=_stable_item_id(source.id, link, title),
                source=source.name,
                source_kind=SourceKind.RSS,
                title=title,
                text=summary,
                url=HttpUrl(link),
                author=clean_feed_text(entry.get("author")) or None,
                published_at=published_at,
                retrieved_at=retrieved_at,
                metadata={
                    "source_id": source.id,
                    "source_tags": list(source.tags),
                },
            )
        )

    return items


def fetch_source(
    client: httpx.Client,
    *,
    source: RssSourceConfig,
    retrieved_at: datetime,
    max_items: int,
    lookback_hours: int | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> tuple[list[SourceItem], NewsSourceDiagnostic]:
    try:
        response = client.get(str(source.url))
        response.raise_for_status()

        if not response.content:
            raise ValueError("empty response")

        items = parse_feed_bytes(
            response.content,
            source=source,
            retrieved_at=retrieved_at,
            max_items=max_items,
            lookback_hours=lookback_hours,
            window_start=window_start,
            window_end=window_end,
        )

        return items, NewsSourceDiagnostic(
            source_id=source.id,
            source_name=source.name,
            url=str(source.url),
            ok=True,
            item_count=len(items),
        )
    except (httpx.HTTPError, ValueError) as exc:
        return [], NewsSourceDiagnostic(
            source_id=source.id,
            source_name=source.name,
            url=str(source.url),
            ok=False,
            item_count=0,
            error=str(exc),
        )


def retrieve_source_set(
    source_set: NewsSourceSet,
    *,
    max_items_per_source: int,
    lookback_hours: int | None = None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    retrieved_at: datetime | None = None,
    timeout_seconds: float = 20.0,
) -> tuple[list[SourceItem], list[NewsSourceDiagnostic]]:
    now = retrieved_at or datetime.now(UTC)
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

            source_items, diagnostic = fetch_source(
                client,
                source=source,
                retrieved_at=now,
                max_items=max_items_per_source,
                lookback_hours=lookback_hours,
                window_start=window_start,
                window_end=window_end,
            )
            items.extend(source_items)
            diagnostics.append(diagnostic)

    return items, diagnostics
