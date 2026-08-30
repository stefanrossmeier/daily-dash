from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd

from daily_dash.config import FuturesAssetConfig, FuturesSourceSet
from daily_dash.retrieval.futures.tradingview import TradingViewFuturesRetriever


class FakeIntervals:
    in_1_hour = "1h"
    in_daily = "1d"


class FakeClient:
    def __init__(self, histories: dict[tuple[str, str], pd.DataFrame | None]) -> None:
        self.histories = histories
        self.calls: list[tuple[str, str, str, int]] = []

    def get_hist(
        self,
        *,
        symbol: str,
        exchange: str,
        interval: str,
        n_bars: int,
    ) -> pd.DataFrame | None:
        self.calls.append((symbol, exchange, interval, n_bars))
        return self.histories.get((symbol, interval))


def _frame(values: list[float], timestamps: list[datetime]) -> pd.DataFrame:
    return pd.DataFrame({"close": values}, index=pd.DatetimeIndex(timestamps))


def _source_set(*assets: FuturesAssetConfig) -> FuturesSourceSet:
    return FuturesSourceSet.model_validate(
        {
            "pipeline": "futures",
            "source_set_id": "futures",
            "provider": "tradingview-datafeed",
            "intraday_bars": 300,
            "daily_bars": 30,
            "fetch_attempts": 2,
            "max_intraday_age_days": 3,
            "assets": [asset.model_dump() for asset in assets],
        }
    )


def _asset() -> FuturesAssetConfig:
    return FuturesAssetConfig.model_validate(
        {
            "id": "sp500",
            "name": "S&P",
            "instrument": "E-mini S&P 500 continuous future",
            "symbol": "ES1!",
            "exchange": "CME_MINI",
        }
    )


def test_tradingview_uses_recent_intraday_last_and_previous_daily_close() -> None:
    now = datetime(2026, 8, 28, 21, 15, tzinfo=UTC)
    client = FakeClient(
        {
            ("ES1!", "1h"): _frame(
                [5090.0, 5100.0],
                [now - timedelta(hours=2), now - timedelta(hours=1)],
            ),
            ("ES1!", "1d"): _frame(
                [4950.0, 5000.0, 5075.0],
                [
                    datetime(2026, 8, 26, tzinfo=UTC),
                    datetime(2026, 8, 27, tzinfo=UTC),
                    datetime(2026, 8, 28, tzinfo=UTC),
                ],
            ),
        }
    )

    snapshot = TradingViewFuturesRetriever(client=client, intervals=FakeIntervals()).retrieve(
        _source_set(_asset()), run_id="run-1", retrieved_at=now
    )

    quote = snapshot.quotes[0]
    assert quote.last == 5100.0
    assert quote.previous_value == 5000.0
    assert quote.change_basis == "previous_close"
    assert quote.data_type == "tradingview_1h"
    assert quote.contract == "CME_MINI:ES1!"
    assert quote.error is None
    assert client.calls == [
        ("ES1!", "CME_MINI", "1h", 300),
        ("ES1!", "CME_MINI", "1d", 30),
    ]


def test_tradingview_uses_latest_daily_close_when_intraday_is_stale() -> None:
    now = datetime(2026, 8, 28, 21, 15, tzinfo=UTC)
    client = FakeClient(
        {
            ("ES1!", "1h"): _frame(
                [4900.0],
                [now - timedelta(days=4)],
            ),
            ("ES1!", "1d"): _frame(
                [5000.0, 5075.0],
                [datetime(2026, 8, 27, tzinfo=UTC), datetime(2026, 8, 28, tzinfo=UTC)],
            ),
        }
    )

    snapshot = TradingViewFuturesRetriever(client=client, intervals=FakeIntervals()).retrieve(
        _source_set(_asset()), run_id="run-1", retrieved_at=now
    )

    quote = snapshot.quotes[0]
    assert quote.last == 5075.0
    assert quote.previous_value == 5000.0
    assert quote.data_type == "tradingview_daily"
    assert quote.error is None


def test_tradingview_uses_latest_daily_bar_when_intraday_quote_predates_daily_bar() -> None:
    now = datetime(2026, 8, 28, 21, 15, tzinfo=UTC)
    client = FakeClient(
        {
            ("ES1!", "1h"): _frame(
                [5050.0],
                [datetime(2026, 8, 27, 20, 0, tzinfo=UTC)],
            ),
            ("ES1!", "1d"): _frame(
                [4950.0, 5000.0],
                [datetime(2026, 8, 27, tzinfo=UTC), datetime(2026, 8, 28, tzinfo=UTC)],
            ),
        }
    )

    snapshot = TradingViewFuturesRetriever(client=client, intervals=FakeIntervals()).retrieve(
        _source_set(_asset()), run_id="run-1", retrieved_at=now
    )

    quote = snapshot.quotes[0]
    assert quote.last == 5050.0
    assert quote.previous_value == 5000.0
    assert quote.data_type == "tradingview_1h"


def test_tradingview_retries_empty_history_and_degrades_one_asset() -> None:
    class EmptyThenFailClient(FakeClient):
        def get_hist(
            self,
            *,
            symbol: str,
            exchange: str,
            interval: str,
            n_bars: int,
        ) -> pd.DataFrame | None:
            self.calls.append((symbol, exchange, interval, n_bars))
            if symbol == "ES1!":
                return None
            raise RuntimeError("TradingView unavailable")

    second = FuturesAssetConfig.model_validate(
        {
            "id": "nasdaq",
            "name": "Nasdaq",
            "instrument": "E-mini Nasdaq-100 continuous future",
            "symbol": "NQ1!",
            "exchange": "CME_MINI",
        }
    )
    client = EmptyThenFailClient({})
    now = datetime(2026, 8, 28, 21, 15, tzinfo=UTC)

    snapshot = TradingViewFuturesRetriever(client=client, intervals=FakeIntervals()).retrieve(
        _source_set(_asset(), second), run_id="run-1", retrieved_at=now
    )

    assert snapshot.quotes[0].last is None
    assert snapshot.quotes[0].error == "no last price"
    assert client.calls.count(("ES1!", "CME_MINI", "1h", 300)) == 2
    assert client.calls.count(("ES1!", "CME_MINI", "1d", 30)) == 2
    assert snapshot.quotes[1].last is None
    assert snapshot.quotes[1].error == "exception: TradingView unavailable"


def test_tvdatafeed_compatibility_shim_updates_stale_quote_protocol(monkeypatch) -> None:
    import sys
    from types import SimpleNamespace

    import daily_dash.retrieval.futures.tradingview as module

    sent: list[tuple[str, list[object]]] = []

    class FakeTvDatafeed:
        def _TvDatafeed__send_message(self, method: str, params: list[object]) -> str:
            sent.append((method, params))
            return "sent"

    fake_module = SimpleNamespace(TvDatafeed=FakeTvDatafeed, Interval=FakeIntervals)
    monkeypatch.setitem(sys.modules, "tvDatafeed", fake_module)

    compatible_class, intervals = module._load_tvdatafeed()
    client = compatible_class()

    assert intervals is FakeIntervals
    assert (
        client._TvDatafeed__send_message(
            "quote_add_symbols",
            ["qs_test", "CME_MINI:ES1!", {"flags": ["force_permission"]}],
        )
        == "sent"
    )
    assert sent == [("quote_add_symbols", ["qs_test", "CME_MINI:ES1!"])]

    assert (
        client._TvDatafeed__send_message("quote_fast_symbols", ["qs_test", "CME_MINI:ES1!"]) is None
    )
    assert sent == [("quote_add_symbols", ["qs_test", "CME_MINI:ES1!"])]

    assert client._TvDatafeed__send_message("create_series", ["cs_test", "s1"]) == "sent"
    assert sent[-1] == ("create_series", ["cs_test", "s1"])


def test_runtime_initializes_tvdatafeed_anonymously(monkeypatch) -> None:
    import daily_dash.retrieval.futures.tradingview as module

    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    class FakeTvDatafeed:
        def __init__(self, *args: object, **kwargs: object) -> None:
            calls.append((args, kwargs))

    monkeypatch.setattr(module, "_load_tvdatafeed", lambda: (FakeTvDatafeed, FakeIntervals))
    retriever = TradingViewFuturesRetriever()

    client, intervals = retriever._runtime()

    assert isinstance(client, FakeTvDatafeed)
    assert intervals is FakeIntervals
    assert calls == [((), {})]


def test_runtime_failure_degrades_all_rows_instead_of_aborting(monkeypatch) -> None:
    source_set = _source_set(_asset())
    retriever = TradingViewFuturesRetriever()

    def broken_runtime():
        raise RuntimeError("tvDatafeed unavailable")

    monkeypatch.setattr(retriever, "_runtime", broken_runtime)
    snapshot = retriever.retrieve(
        source_set,
        run_id="run-1",
        retrieved_at=datetime(2026, 8, 28, 21, 0, tzinfo=UTC),
    )

    assert len(snapshot.quotes) == 1
    assert snapshot.quotes[0].last is None
    assert snapshot.quotes[0].error == "exception: tvDatafeed unavailable"
    assert snapshot.quotes[0].source_ref == "CME_MINI:ES1!"


def test_configured_tradingview_universe_matches_legacy_report() -> None:
    from daily_dash.config import default_config_dir, load_futures_source_set

    source_set = load_futures_source_set(default_config_dir() / "sources" / "futures.yaml")
    configured = [
        (asset.name, asset.symbol, asset.exchange, asset.price_decimals)
        for asset in source_set.assets
    ]
    assert configured == [
        ("S&P", "ES1!", "CME_MINI", 2),
        ("Nasdaq", "NQ1!", "CME_MINI", 2),
        ("Dow", "YM1!", "CBOT_MINI", 2),
        ("Stoxx50", "FESX1!", "EUREX", 2),
        ("DAX", "FDAX1!", "EUREX", 2),
        ("Stoxx600", "FXXP1!", "EUREX", 2),
        ("HSI", "HSI1!", "HKEX", 2),
        ("Nikkei", "NIY1!", "CME", 2),
        ("MSCI World", "MWL1!", "ICEUS", 2),
        ("CSI500", "IC1!", "CFFEX", 2),
        ("EURUSD", "E71!", "CME_MINI", 4),
        ("EURCHF", "RF1!", "CME", 4),
        ("US 10Y", "10Y1!", "CBOT_MINI", 3),
        ("Schatz", "FGBS1!", "EUREX", 3),
        ("Gold", "GC1!", "COMEX", 2),
        ("Silver", "SI1!", "COMEX", 3),
        ("Brent", "BZ1!", "NYMEX", 2),
        ("WTI", "CL1!", "NYMEX", 2),
        ("Bitcoin", "BTC1!", "CME", 2),
        ("Ethereum", "ETH1!", "CME", 2),
    ]
