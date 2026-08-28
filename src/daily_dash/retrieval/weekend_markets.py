from __future__ import annotations

import html as html_lib
import json
import re
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

import httpx

from daily_dash.config import WeekendMarketQuoteConfig, WeekendMarketSourceSet
from daily_dash.contracts import RawWeekendMarketQuote, RawWeekendMarketSnapshot

_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_STYLE_RE = re.compile(r"<style\b[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
_SELL_RE = re.compile(r"(?:\bVerkauf\b|\bSELL\b)\s+([0-9]+(?:[.,][0-9]+)?)", re.IGNORECASE)
_BUY_RE = re.compile(r"(?:\bKauf\b|\bBUY\b)\s+([0-9]+(?:[.,][0-9]+)?)", re.IGNORECASE)
_CHANGE_PAIR_RE = re.compile(r"([+\-−]?\d+(?:[.,]\d+)?)\s*\(\s*([+\-−]?\d+(?:[.,]\d+)?)\s*%\s*\)")


class WeekendMarketRetriever(Protocol):
    def retrieve(
        self,
        source_set: WeekendMarketSourceSet,
        *,
        run_id: str,
        retrieved_at: datetime,
    ) -> RawWeekendMarketSnapshot: ...


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).replace("\u00a0", " ").replace("−", "-").strip().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _visible_text(markup: str) -> str:
    text = _SCRIPT_RE.sub(" ", markup)
    text = _STYLE_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    text = html_lib.unescape(text).replace("\u00a0", " ").replace("−", "-")
    return re.sub(r"\s+", " ", text).strip()


def _parse_visible_quote(markup: str) -> tuple[float | None, float | None, float | None]:
    text = _visible_text(markup)
    sell_match = _SELL_RE.search(text)
    buy_match = _BUY_RE.search(text)
    bid = _to_float(sell_match.group(1)) if sell_match else None
    ask = _to_float(buy_match.group(1)) if buy_match else None

    change_pct: float | None = None
    start = buy_match.end() if buy_match else 0
    change_match = _CHANGE_PAIR_RE.search(text, start, min(len(text), start + 500))
    if change_match is None:
        change_match = _CHANGE_PAIR_RE.search(text)
    if change_match is not None:
        change_pct = _to_float(change_match.group(2))

    return bid, ask, change_pct


def _find_quote_dicts(value: object) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    if isinstance(value, dict):
        lowered = {str(key).lower() for key in value}
        interesting = {
            "bid",
            "offer",
            "ask",
            "sell",
            "buy",
            "percentagechange",
            "percentchange",
            "pctchange",
            "changepct",
            "changepercent",
        }
        if len(lowered & interesting) >= 2:
            results.append({str(key): item for key, item in value.items()})
        for item in value.values():
            results.extend(_find_quote_dicts(item))
    elif isinstance(value, list):
        for item in value:
            results.extend(_find_quote_dicts(item))
    return results


def _dict_value(container: dict[str, object], names: tuple[str, ...]) -> object:
    lowered = {key.lower(): key for key in container}
    for name in names:
        key = lowered.get(name.lower())
        if key is not None:
            return container[key]
    return None


def _parse_next_data_quote(markup: str) -> tuple[float | None, float | None, float | None]:
    match = _NEXT_DATA_RE.search(markup)
    if match is None:
        return None, None, None

    try:
        payload: object = json.loads(html_lib.unescape(match.group(1)).strip())
    except (json.JSONDecodeError, TypeError):
        return None, None, None

    best: tuple[float | None, float | None, float | None] = (None, None, None)
    best_score = -1
    for candidate in _find_quote_dicts(payload):
        bid = _to_float(_dict_value(candidate, ("bid", "sell")))
        ask = _to_float(_dict_value(candidate, ("offer", "ask", "buy")))
        change_pct = _to_float(
            _dict_value(
                candidate,
                (
                    "percentageChange",
                    "percentChange",
                    "pctChange",
                    "changePct",
                    "changePercent",
                ),
            )
        )
        score = sum(value is not None for value in (bid, ask)) * 2 + (change_pct is not None) * 3
        if score > best_score:
            best = bid, ask, change_pct
            best_score = score
    return best


def parse_ig_weekend_quote(markup: str) -> tuple[float | None, float | None, float | None]:
    """Extract bid, ask and percentage change from an IG weekend market page."""
    visible = _parse_visible_quote(markup)
    if all(value is not None for value in visible):
        return visible

    structured = _parse_next_data_quote(markup)
    return (
        visible[0] if visible[0] is not None else structured[0],
        visible[1] if visible[1] is not None else structured[1],
        visible[2] if visible[2] is not None else structured[2],
    )


class IgWeekendMarketRetriever:
    """Retrieve public no-login weekend quotes from IG market pages."""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 25.0,
        user_agent: str = "daily-dash-weekend-markets/1.0",
        fetcher: Callable[[str], str] | None = None,
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent
        self._fetcher = fetcher

    def _fetch(self, url: str) -> str:
        if self._fetcher is not None:
            return self._fetcher(url)

        own_client = self._client is None
        client = self._client or httpx.Client(
            timeout=self._timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": self._user_agent},
        )
        try:
            response = client.get(url)
            response.raise_for_status()
            return response.text
        finally:
            if own_client:
                client.close()

    def _retrieve_quote(self, quote: WeekendMarketQuoteConfig) -> RawWeekendMarketQuote:
        url = str(quote.url)
        try:
            markup = self._fetch(url)
            bid, ask, change_pct = parse_ig_weekend_quote(markup)
        except (httpx.HTTPError, ValueError) as exc:
            return RawWeekendMarketQuote(
                quote_id=quote.id,
                name=quote.name,
                url=url,
                price_decimals=quote.price_decimals,
                error=f"retrieval failed: {exc}",
            )

        missing = [
            label
            for label, value in (("bid", bid), ("ask", ask), ("change", change_pct))
            if value is None
        ]
        error = f"missing {', '.join(missing)}" if missing else None
        return RawWeekendMarketQuote(
            quote_id=quote.id,
            name=quote.name,
            url=url,
            price_decimals=quote.price_decimals,
            bid=bid,
            ask=ask,
            change_pct=change_pct,
            error=error,
        )

    def retrieve(
        self,
        source_set: WeekendMarketSourceSet,
        *,
        run_id: str,
        retrieved_at: datetime,
    ) -> RawWeekendMarketSnapshot:
        quotes = [self._retrieve_quote(quote) for quote in source_set.quotes if quote.enabled]
        return RawWeekendMarketSnapshot(
            run_id=run_id,
            source_set=source_set.source_set_id,
            retrieved_at=retrieved_at,
            quotes=quotes,
        )
