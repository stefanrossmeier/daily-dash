from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from daily_dash.config import FuturesAssetConfig, FuturesSourceSet
from daily_dash.contracts.futures import RawFuturesQuote, RawFuturesSnapshot

BERLIN = ZoneInfo("Europe/Berlin")


class TradingViewHistoryClient(Protocol):
    def get_hist(
        self,
        *,
        symbol: str,
        exchange: str,
        interval: Any,
        n_bars: int,
    ) -> Any: ...


class TradingViewIntervals(Protocol):
    in_1_hour: Any
    in_daily: Any


def _load_tvdatafeed() -> tuple[type[Any], TradingViewIntervals]:
    try:
        from tvDatafeed import Interval, TvDatafeed  # type: ignore[import-untyped]
    except Exception as exc:  # pragma: no cover - exercised only in a broken runtime image
        raise RuntimeError(f"tvDatafeed import failed: {exc}") from exc

    class CompatibleTvDatafeed(TvDatafeed):  # type: ignore[misc]
        """Adapt tvDatafeed 2.1.1 to TradingView's current anonymous quote protocol."""

        def _TvDatafeed__send_message(self, method: str, params: list[Any]) -> Any:
            if method == "quote_add_symbols" and len(params) == 3:
                params = params[:2]
            elif method == "quote_fast_symbols":
                return None
            return super()._TvDatafeed__send_message(method, params)

    return CompatibleTvDatafeed, Interval


def _to_berlin(value: object | None) -> datetime | None:
    if value is None:
        return None
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(BERLIN)


def _history_with_close(
    client: TradingViewHistoryClient,
    *,
    asset: FuturesAssetConfig,
    interval: Any,
    n_bars: int,
    fetch_attempts: int,
) -> Any | None:
    for _ in range(fetch_attempts):
        history = client.get_hist(
            symbol=asset.symbol,
            exchange=asset.exchange,
            interval=interval,
            n_bars=n_bars,
        )
        if history is None or history.empty:
            continue
        for column in ("close", "Close"):
            if column in history:
                closes = history[column].dropna()
                if not closes.empty:
                    return closes
    return None


def _quote_for_asset(
    client: TradingViewHistoryClient,
    intervals: TradingViewIntervals,
    asset: FuturesAssetConfig,
    source_set: FuturesSourceSet,
    *,
    retrieved_at: datetime,
) -> RawFuturesQuote:
    source_ref = f"{asset.exchange}:{asset.symbol}"
    try:
        intraday = _history_with_close(
            client,
            asset=asset,
            interval=intervals.in_1_hour,
            n_bars=source_set.intraday_bars,
            fetch_attempts=source_set.fetch_attempts,
        )
        daily = _history_with_close(
            client,
            asset=asset,
            interval=intervals.in_daily,
            n_bars=source_set.daily_bars,
            fetch_attempts=source_set.fetch_attempts,
        )

        last: float | None = None
        last_timestamp: datetime | None = None
        used_intraday = False
        intraday_timestamp = _to_berlin(intraday.index[-1]) if intraday is not None else None
        if intraday is not None and intraday_timestamp is not None:
            reference = retrieved_at.astimezone(BERLIN)
            if reference - intraday_timestamp <= timedelta(days=source_set.max_intraday_age_days):
                last = float(intraday.iloc[-1])
                last_timestamp = intraday_timestamp
                used_intraday = True

        if daily is None:
            return RawFuturesQuote(
                asset_id=asset.id,
                name=asset.name,
                instrument=asset.instrument,
                price_decimals=asset.price_decimals,
                contract=source_ref,
                last=last,
                change_basis="unavailable",
                source="TradingView",
                source_ref=source_ref,
                source_timestamp=last_timestamp,
                data_type="tradingview_1h" if last_timestamp is not None else None,
                error="no previous close" if last is not None else "no last price",
            )

        if last is None:
            last = float(daily.iloc[-1])
            last_timestamp = _to_berlin(daily.index[-1])
            previous = float(daily.iloc[-2]) if len(daily) >= 2 else None
        else:
            last_daily_timestamp = _to_berlin(daily.index[-1])
            quote_date = last_timestamp.date() if last_timestamp is not None else None
            daily_date = last_daily_timestamp.date() if last_daily_timestamp is not None else None
            if quote_date is not None and daily_date is not None and quote_date >= daily_date:
                previous = float(daily.iloc[-2]) if len(daily) >= 2 else None
            else:
                previous = float(daily.iloc[-1]) if len(daily) >= 1 else None

        return RawFuturesQuote(
            asset_id=asset.id,
            name=asset.name,
            instrument=asset.instrument,
            price_decimals=asset.price_decimals,
            contract=source_ref,
            last=last,
            previous_value=previous,
            change_basis="previous_close" if previous is not None else "unavailable",
            source="TradingView",
            source_ref=source_ref,
            source_timestamp=last_timestamp,
            data_type="tradingview_1h" if used_intraday else "tradingview_daily",
            error=None if previous is not None else "no previous close",
        )
    except Exception as exc:
        return RawFuturesQuote(
            asset_id=asset.id,
            name=asset.name,
            instrument=asset.instrument,
            price_decimals=asset.price_decimals,
            contract=source_ref,
            source="TradingView",
            source_ref=source_ref,
            error=f"exception: {exc}",
        )


class TradingViewFuturesRetriever:
    """Translate the historical DailyDash anonymous tvDatafeed Futures report."""

    def __init__(
        self,
        *,
        client: TradingViewHistoryClient | None = None,
        intervals: TradingViewIntervals | None = None,
    ) -> None:
        self._client = client
        self._intervals = intervals

    def _runtime(self) -> tuple[TradingViewHistoryClient, TradingViewIntervals]:
        if self._client is not None and self._intervals is not None:
            return self._client, self._intervals
        tv_class, intervals = _load_tvdatafeed()
        return tv_class(), intervals

    def retrieve(
        self,
        source_set: FuturesSourceSet,
        *,
        run_id: str,
        retrieved_at: datetime,
    ) -> RawFuturesSnapshot:
        enabled_assets = [asset for asset in source_set.assets if asset.enabled]
        try:
            client, intervals = self._runtime()
        except Exception as exc:
            error = f"exception: {exc}"
            quotes = [
                RawFuturesQuote(
                    asset_id=asset.id,
                    name=asset.name,
                    instrument=asset.instrument,
                    price_decimals=asset.price_decimals,
                    contract=f"{asset.exchange}:{asset.symbol}",
                    source="TradingView",
                    source_ref=f"{asset.exchange}:{asset.symbol}",
                    error=error,
                )
                for asset in enabled_assets
            ]
        else:
            quotes = [
                _quote_for_asset(
                    client,
                    intervals,
                    asset,
                    source_set,
                    retrieved_at=retrieved_at,
                )
                for asset in enabled_assets
            ]
        return RawFuturesSnapshot(
            run_id=run_id,
            source_set=source_set.source_set_id,
            retrieved_at=retrieved_at,
            quotes=quotes,
        )
