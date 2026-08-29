from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

import httpx

from daily_dash.config.models import PolymarketRetrievalConfig, PolymarketSourceSet
from daily_dash.contracts.polymarket import (
    PolymarketEvent,
    PolymarketEventMarket,
    PolymarketRetrievalDiagnostic,
)

_TIMEOUT_SECONDS = 25.0


def _safe_float(value: object) -> float | None:
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _safe_int(value: object) -> int | None:
    if not isinstance(value, (int, float, str)):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _safe_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _string_list(value: object) -> list[str]:
    raw = value
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if str(item).strip()]


def _float_list(value: object) -> list[float]:
    out: list[float] = []
    for item in _string_list(value):
        parsed = _safe_float(item)
        if parsed is not None and 0.0 <= parsed <= 1.0:
            out.append(parsed)
    return out


def _normalize_market(raw: dict[str, Any]) -> PolymarketEventMarket | None:
    question = str(raw.get("question") or "").strip()
    condition_id = str(raw.get("conditionId") or "").strip()
    if not question or not condition_id:
        return None
    if raw.get("closed") or raw.get("archived") or raw.get("active") is False:
        return None
    if raw.get("acceptingOrders") is False:
        return None

    outcomes = _string_list(raw.get("outcomes"))
    prices = _float_list(raw.get("outcomePrices"))
    top_outcome: str | None = None
    top_probability: float | None = None
    if prices:
        top_index = max(range(len(prices)), key=prices.__getitem__)
        top_probability = prices[top_index]
        if top_index < len(outcomes):
            top_outcome = outcomes[top_index]

    slug_raw = raw.get("slug")
    return PolymarketEventMarket(
        question=question,
        condition_id=condition_id,
        slug=str(slug_raw).strip() if slug_raw else None,
        outcomes=outcomes,
        outcome_prices=prices,
        top_outcome=top_outcome,
        top_probability=top_probability,
        volume_24h=max(_safe_float(raw.get("volume24hr")) or 0.0, 0.0),
        one_hour_price_change=_safe_float(raw.get("oneHourPriceChange")) or 0.0,
        one_day_price_change=_safe_float(raw.get("oneDayPriceChange")) or 0.0,
    )


def _event_tags(raw: dict[str, Any]) -> list[str]:
    tags = raw.get("tags")
    if not isinstance(tags, list):
        return []
    out: list[str] = []
    for item in tags:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "").strip().lower()
        if slug and slug not in out:
            out.append(slug)
    return out


def _event_category(raw: dict[str, Any]) -> str | None:
    category = raw.get("category")
    if category:
        return str(category).strip() or None
    categories = raw.get("categories")
    if isinstance(categories, list):
        for item in categories:
            if not isinstance(item, dict):
                continue
            slug = str(item.get("slug") or item.get("label") or "").strip()
            if slug:
                return slug
    return None


def _event_key(event_id: int, slug: str) -> str:
    return sha256(f"{event_id}:{slug}".encode()).hexdigest()[:24]


def _normalize_event(raw: dict[str, Any]) -> PolymarketEvent | None:
    event_id = _safe_int(raw.get("id"))
    title = str(raw.get("title") or "").strip()
    slug = str(raw.get("slug") or "").strip()
    if event_id is None or event_id < 1 or not title or not slug:
        return None
    if raw.get("closed") or raw.get("archived") or raw.get("active") is False:
        return None

    raw_markets_value = raw.get("markets")
    raw_markets = raw_markets_value if isinstance(raw_markets_value, list) else []
    markets: list[PolymarketEventMarket] = []
    for item in raw_markets:
        if not isinstance(item, dict):
            continue
        market = _normalize_market(item)
        if market is not None:
            markets.append(market)
    if not markets:
        return None

    event_volume = _safe_float(raw.get("volume24hr"))
    event_liquidity = _safe_float(raw.get("liquidity"))
    volume_24h = max(event_volume or sum(item.volume_24h for item in markets), 0.0)
    liquidity = max(event_liquidity or 0.0, 0.0)
    if liquidity <= 0.0:
        raw_liquidities = [
            _safe_float(item.get("liquidityNum")) for item in raw_markets if isinstance(item, dict)
        ]
        liquidity = sum(value for value in raw_liquidities if value and value > 0.0)

    return PolymarketEvent(
        id=_event_key(event_id, slug),
        event_id=event_id,
        title=title,
        description=str(raw.get("description") or "").strip(),
        url=f"https://polymarket.com/event/{slug}",
        slug=slug,
        category=_event_category(raw),
        tags=_event_tags(raw),
        start_at=_safe_datetime(raw.get("startDate")),
        end_at=_safe_datetime(raw.get("endDate")),
        volume_24h=volume_24h,
        liquidity=liquidity,
        comment_count=max(_safe_int(raw.get("commentCount")) or 0, 0),
        max_abs_one_hour_price_change=max(
            (abs(item.one_hour_price_change) for item in markets), default=0.0
        ),
        max_abs_one_day_price_change=max(
            (abs(item.one_day_price_change) for item in markets), default=0.0
        ),
        markets=markets,
    )


def _fetch_events(
    client: httpx.Client,
    source_set: PolymarketSourceSet,
    config: PolymarketRetrievalConfig,
    *,
    limit: int,
    tag_slug: str | None = None,
) -> list[PolymarketEvent]:
    params: dict[str, str | int | float | bool | None] = {
        "limit": limit,
        "offset": 0,
        "order": "volume24hr",
        "ascending": "false",
        "active": "true",
        "closed": "false",
        "liquidity_min": config.liquidity_min,
    }
    if tag_slug:
        params["tag_slug"] = tag_slug
        params["related_tags"] = "true"
    response = client.get(str(source_set.gamma_events_url), params=params)
    response.raise_for_status()
    raw = response.json()
    if not isinstance(raw, list):
        raise ValueError("events response was not a JSON array")
    out: list[PolymarketEvent] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        event = _normalize_event(item)
        if event is None or event.id in seen:
            continue
        seen.add(event.id)
        out.append(event)
    return out


def _round_robin_semantic_events(
    by_tag: dict[str, list[PolymarketEvent]],
    *,
    limit: int,
) -> list[PolymarketEvent]:
    if limit <= 0:
        return []
    out: list[PolymarketEvent] = []
    seen: set[str] = set()
    index = 0
    ordered_tags = list(by_tag)
    while len(out) < limit:
        added = False
        for tag in ordered_tags:
            rows = by_tag[tag]
            if index >= len(rows):
                continue
            event = rows[index]
            if event.id in seen:
                continue
            seen.add(event.id)
            out.append(event)
            added = True
            if len(out) >= limit:
                break
        if not added and all(index >= len(by_tag[tag]) - 1 for tag in ordered_tags):
            break
        index += 1
    return out


def _fetch_recent_event_trade_counts(
    client: httpx.Client,
    source_set: PolymarketSourceSet,
    config: PolymarketRetrievalConfig,
    events: list[PolymarketEvent],
    *,
    retrieved_at: datetime,
) -> tuple[dict[str, int], int, int, bool, bool, list[str]]:
    if not events:
        return {}, 0, 0, True, True, []

    window_end = retrieved_at.astimezone(UTC)
    window_start = window_end - timedelta(minutes=config.trade_window_minutes)
    start_epoch = int(window_start.timestamp())
    end_epoch = int(window_end.timestamp())
    slug_to_id = {item.slug: item.id for item in events}
    condition_to_id = {
        market.condition_id: event.id for event in events for market in event.markets
    }
    counts = {item.id: 0 for item in events}
    total = 0
    pages = 0
    all_complete = True
    all_ok = True
    errors: list[str] = []

    for batch_start in range(0, len(events), config.trade_event_batch_size):
        batch = events[batch_start : batch_start + config.trade_event_batch_size]
        event_ids = ",".join(str(item.event_id) for item in batch)
        batch_complete = False
        batch_ok = True

        for page in range(config.max_trade_pages):
            offset = page * config.trade_page_limit
            try:
                response = client.get(
                    str(source_set.data_trades_url),
                    params={
                        "limit": config.trade_page_limit,
                        "offset": offset,
                        "eventId": event_ids,
                        "start": start_epoch,
                        "end": end_epoch,
                    },
                )
                response.raise_for_status()
                raw = response.json()
            except Exception as exc:
                errors.append(f"trades[{event_ids}]: {type(exc).__name__}: {exc}")
                batch_ok = False
                break

            pages += 1
            if not isinstance(raw, list):
                errors.append(f"trades[{event_ids}]: response was not a JSON array")
                batch_ok = False
                break

            for trade in raw:
                if not isinstance(trade, dict):
                    continue
                try:
                    timestamp = datetime.fromtimestamp(
                        int(trade.get("timestamp") or 0),
                        tz=UTC,
                    )
                except (TypeError, ValueError, OSError):
                    continue
                if timestamp < window_start or timestamp > window_end:
                    continue
                event_key = slug_to_id.get(str(trade.get("eventSlug") or "").strip())
                if event_key is None:
                    event_key = condition_to_id.get(str(trade.get("conditionId") or "").strip())
                if event_key is None:
                    continue
                counts[event_key] = counts.get(event_key, 0) + 1
                total += 1

            if len(raw) < config.trade_page_limit:
                batch_complete = True
                break

        all_ok = all_ok and batch_ok
        all_complete = all_complete and batch_ok and batch_complete

    return counts, total, pages, all_complete, all_ok, errors


def retrieve_polymarket_events(
    source_set: PolymarketSourceSet,
    config: PolymarketRetrievalConfig,
    *,
    retrieved_at: datetime,
) -> tuple[list[PolymarketEvent], list[PolymarketEvent], list[PolymarketRetrievalDiagnostic]]:
    """Retrieve a small semantic event pool plus a global no-LLM hot-event pool."""

    errors: list[str] = []
    by_tag: dict[str, list[PolymarketEvent]] = {}
    global_events: list[PolymarketEvent] = []
    tag_successes = 0
    headers = {"User-Agent": source_set.user_agent, "Accept": "application/json"}

    with httpx.Client(timeout=_TIMEOUT_SECONDS, follow_redirects=True, headers=headers) as client:
        for tag in config.semantic_tag_slugs:
            try:
                by_tag[tag] = _fetch_events(
                    client,
                    source_set,
                    config,
                    limit=config.semantic_event_limit_per_tag,
                    tag_slug=tag,
                )
                tag_successes += 1
            except Exception as exc:
                by_tag[tag] = []
                errors.append(f"events[{tag}]: {type(exc).__name__}: {exc}")

        try:
            global_events = _fetch_events(
                client,
                source_set,
                config,
                limit=config.global_event_limit,
            )
        except Exception as exc:
            errors.append(f"events[global]: {type(exc).__name__}: {exc}")

        semantic_candidates = _round_robin_semantic_events(
            by_tag,
            limit=config.candidate_limit,
        )
        hot_candidates = global_events[: config.hot_activity_pool_limit]
        trade_counts, trade_count, trade_pages, trade_complete, trades_ok, trade_errors = (
            _fetch_recent_event_trade_counts(
                client,
                source_set,
                config,
                hot_candidates,
                retrieved_at=retrieved_at,
            )
        )
        errors.extend(trade_errors)

    hot_candidates = [
        item.model_copy(update={"recent_trades": trade_counts.get(item.id, 0)})
        for item in hot_candidates
    ]
    unique_events = {item.id for rows in by_tag.values() for item in rows}
    unique_events.update(item.id for item in global_events)
    semantic_unique = {item.id for rows in by_tag.values() for item in rows}
    diagnostic = PolymarketRetrievalDiagnostic(
        events_ok=tag_successes > 0 and bool(global_events),
        trades_ok=trades_ok,
        semantic_tag_requests=len(config.semantic_tag_slugs),
        semantic_event_count=len(semantic_unique),
        global_event_count=len(global_events),
        unique_event_count=len(unique_events),
        trade_scope_event_count=len(hot_candidates),
        trade_count=trade_count,
        trade_pages=trade_pages,
        trade_window_minutes=config.trade_window_minutes,
        trade_window_complete=trade_complete,
        errors=errors,
    )
    return semantic_candidates, hot_candidates, [diagnostic]


def check_polymarket_access(
    source_set: PolymarketSourceSet,
    config: PolymarketRetrievalConfig,
) -> dict[str, object]:
    """Cheap public-API validation for Gamma events and event-scoped Data API trades."""

    headers = {"User-Agent": source_set.user_agent, "Accept": "application/json"}
    with httpx.Client(timeout=_TIMEOUT_SECONDS, follow_redirects=True, headers=headers) as client:
        events_response = client.get(
            str(source_set.gamma_events_url),
            params={
                "limit": 1,
                "offset": 0,
                "order": "volume24hr",
                "ascending": "false",
                "active": "true",
                "closed": "false",
                "liquidity_min": config.liquidity_min,
            },
        )
        events_response.raise_for_status()
        events = events_response.json()
        if not isinstance(events, list) or not events:
            raise RuntimeError("Polymarket events API returned no sample event")
        event_id = _safe_int(events[0].get("id") if isinstance(events[0], dict) else None)
        if event_id is None:
            raise RuntimeError("Polymarket sample event did not contain an integer id")
        check_end = datetime.now(UTC)
        check_start = check_end - timedelta(minutes=config.trade_window_minutes)
        trades_response = client.get(
            str(source_set.data_trades_url),
            params={
                "limit": 1,
                "offset": 0,
                "eventId": str(event_id),
                "start": int(check_start.timestamp()),
                "end": int(check_end.timestamp()),
            },
        )
        trades_response.raise_for_status()
        trades = trades_response.json()
    if not isinstance(trades, list):
        raise RuntimeError("Polymarket trades API validation returned an unexpected payload")
    return {
        "status": "ok",
        "provider": source_set.provider,
        "sample_events": len(events),
        "sample_trades": len(trades),
    }
