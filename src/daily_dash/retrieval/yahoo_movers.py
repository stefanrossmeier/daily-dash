from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

import yfinance as yf  # type: ignore[import-untyped]

from daily_dash.config import MoverCategoryConfig, YahooMoversSourceSet
from daily_dash.contracts import RawMoverCategory, RawMoverEntry, RawMoverSnapshot

Screen = Callable[[str, int], dict[str, Any]]


class YahooMoversRetriever(Protocol):
    def retrieve(
        self,
        source_set: YahooMoversSourceSet,
        *,
        run_id: str,
        retrieved_at: datetime,
    ) -> RawMoverSnapshot:
        """Retrieve every configured Yahoo Finance screener category."""


def _to_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    number = _to_float(value)
    return None if number is None else int(number)


def _entries(payload: dict[str, Any], *, limit: int) -> list[RawMoverEntry]:
    quotes = payload.get("quotes")
    if not isinstance(quotes, list):
        return []

    entries: list[RawMoverEntry] = []
    for quote in quotes[:limit]:
        if not isinstance(quote, dict):
            continue
        symbol = str(quote.get("symbol") or "").strip()
        name = str(quote.get("shortName") or quote.get("longName") or symbol).strip()
        price = _to_float(quote.get("regularMarketPrice"))
        change_pct = _to_float(quote.get("regularMarketChangePercent"))
        if not symbol or price is None or change_pct is None:
            continue
        entries.append(
            RawMoverEntry(
                symbol=symbol,
                name=name,
                price=price,
                change_pct=change_pct,
                volume=_to_int(quote.get("regularMarketVolume")),
            )
        )
    return entries


def _default_screen(screener: str, count: int) -> dict[str, Any]:
    payload: dict[str, Any] = yf.screen(screener, count=count)
    return payload


class OfficialYahooMoversRetriever:
    """Retrieve Yahoo Finance predefined screener results via yfinance."""

    def __init__(self, *, screen: Screen | None = None, timeout_seconds: float = 30.0) -> None:
        self._screen = screen or _default_screen
        self._timeout_seconds = timeout_seconds

    def _retrieve_category(
        self,
        config: MoverCategoryConfig,
        *,
        count: int,
    ) -> RawMoverCategory:
        try:
            payload = self._screen(config.screener, count)
            movers = _entries(payload, limit=count)
            if not movers:
                raise ValueError("no screener results returned")
            return RawMoverCategory(
                category_id=config.id,
                name=config.name,
                screener=config.screener,
                movers=movers,
            )
        except Exception as exc:
            return RawMoverCategory(
                category_id=config.id,
                name=config.name,
                screener=config.screener,
                error=f"{type(exc).__name__}: {exc}",
            )

    def retrieve(
        self,
        source_set: YahooMoversSourceSet,
        *,
        run_id: str,
        retrieved_at: datetime,
    ) -> RawMoverSnapshot:
        # Request a few extra rows so entries with missing quote fields can
        # be dropped without shrinking the rendered top-n below the target.
        count = source_set.top_n + 5
        categories = [
            self._retrieve_category(config, count=count)
            for config in source_set.categories
            if config.enabled
        ]
        return RawMoverSnapshot(
            run_id=run_id,
            source_set=source_set.source_set_id,
            retrieved_at=retrieved_at,
            categories=categories,
        )
