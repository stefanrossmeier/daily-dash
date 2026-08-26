from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

import yfinance as yf  # type: ignore[import-untyped]

from daily_dash.config import MarketAssetConfig, MarketSourceSet
from daily_dash.contracts.market import RawMarketAsset, RawMarketSnapshot

logger = logging.getLogger(__name__)


class MarketRetriever(Protocol):
    def retrieve(
        self,
        source_set: MarketSourceSet,
        *,
        run_id: str,
        retrieved_at: datetime,
    ) -> RawMarketSnapshot: ...


class YahooFinanceRetriever:
    """Retrieve market facts from Yahoo Finance via yfinance."""

    def __init__(self, ticker_factory: Callable[[str], Any] | None = None) -> None:
        self._ticker_factory = ticker_factory or yf.Ticker

    @staticmethod
    def _numeric_value(container: Any, *keys: str) -> float | None:
        for key in keys:
            value: Any = None

            try:
                value = getattr(container, key, None)
            except Exception:
                value = None

            if value is None:
                try:
                    getter = getattr(container, "get", None)
                    if getter is not None:
                        value = getter(key)
                except Exception:
                    value = None

            if value is None:
                continue

            try:
                return float(value)
            except (TypeError, ValueError):
                continue

        return None

    @staticmethod
    def _close_values(frame: Any) -> list[float]:
        if frame is None or bool(getattr(frame, "empty", True)):
            return []

        try:
            if "Close" not in frame:
                return []
            series = frame["Close"].dropna()
            values = series.tolist()
        except Exception:
            return []

        result: list[float] = []
        for value in values:
            try:
                result.append(float(value))
            except (TypeError, ValueError):
                continue
        return result

    def _last_and_previous_close(self, symbol: str) -> tuple[float | None, float | None]:
        ticker = self._ticker_factory(symbol)

        try:
            fast_info = ticker.fast_info
            fast_last = self._numeric_value(fast_info, "last_price", "lastPrice")
            previous = self._numeric_value(fast_info, "previous_close", "previousClose")
            if fast_last is not None and previous not in (None, 0.0):
                return fast_last, previous
        except Exception as exc:
            logger.warning("fast_info failed for %s: %s", symbol, exc)

        last: float | None = None

        for interval, period in (("5m", "5d"), ("15m", "1mo"), ("60m", "3mo")):
            try:
                history = ticker.history(interval=interval, period=period, auto_adjust=False)
                closes = self._close_values(history)
                if closes:
                    last = closes[-1]
                    break
            except Exception as exc:
                logger.warning(
                    "intraday history failed for %s (%s, %s): %s",
                    symbol,
                    interval,
                    period,
                    exc,
                )

        try:
            daily = ticker.history(interval="1d", period="6mo", auto_adjust=False)
            daily_closes = self._close_values(daily)
        except Exception as exc:
            logger.warning("daily history failed for %s: %s", symbol, exc)
            daily_closes = []

        if not daily_closes:
            return last, None

        if last is None:
            last = daily_closes[-1]

        previous = daily_closes[-2] if len(daily_closes) >= 2 else None
        return last, previous

    def _ath_facts(
        self,
        symbol: str,
        period: str,
    ) -> tuple[float | None, float | None, str | None]:
        try:
            ticker = self._ticker_factory(symbol)
            history = ticker.history(period=period, interval="1d", auto_adjust=False)
            closes = self._close_values(history)
        except Exception as exc:
            logger.warning("ATH history failed for %s (%s): %s", symbol, period, exc)
            return None, None, f"exception: {exc}"

        if not closes:
            return None, None, "no ATH history"

        high = max(closes)
        if high <= 0:
            return closes[-1], None, "invalid ATH"

        return closes[-1], high, None

    def _retrieve_asset(self, asset: MarketAssetConfig) -> RawMarketAsset:
        error: str | None = None

        try:
            last, previous = self._last_and_previous_close(asset.symbol)
        except Exception as exc:
            logger.exception("market retrieval failed for %s", asset.symbol)
            last = None
            previous = None
            error = f"exception: {exc}"
        else:
            if last is None:
                error = "no last price"
            elif previous in (None, 0.0):
                error = "no prev close"
            else:
                error = None

        ath_last: float | None = None
        ath_high: float | None = None
        ath_error: str | None = None
        ath_symbol: str | None = None
        ath_period: str | None = None
        ath_label: str | None = None

        if asset.ath is not None:
            ath_symbol = asset.ath.symbol
            ath_period = asset.ath.period
            ath_label = asset.ath.label or asset.name
            ath_last, ath_high, ath_error = self._ath_facts(ath_symbol, ath_period)

        return RawMarketAsset(
            asset_id=asset.id,
            name=asset.name,
            symbol=asset.symbol,
            group=asset.group,
            price_decimals=asset.price_decimals,
            last=last,
            previous_close=previous,
            error=error,
            ath_label=ath_label,
            ath_symbol=ath_symbol,
            ath_period=ath_period,
            ath_last=ath_last,
            ath_high=ath_high,
            ath_error=ath_error,
        )

    def retrieve(
        self,
        source_set: MarketSourceSet,
        *,
        run_id: str,
        retrieved_at: datetime,
    ) -> RawMarketSnapshot:
        assets = [self._retrieve_asset(asset) for asset in source_set.assets if asset.enabled]

        return RawMarketSnapshot(
            run_id=run_id,
            source_set=source_set.source_set_id,
            retrieved_at=retrieved_at,
            assets=assets,
        )
