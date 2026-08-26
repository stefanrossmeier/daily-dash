from datetime import UTC, datetime
from typing import Any

from daily_dash.config import MarketSourceSet
from daily_dash.retrieval.markets import YahooFinanceRetriever


class FakeSeries:
    def __init__(self, values: list[float]) -> None:
        self._values = values

    def dropna(self) -> "FakeSeries":
        return self

    def tolist(self) -> list[float]:
        return self._values


class FakeFrame:
    def __init__(self, closes: list[float]) -> None:
        self._closes = closes
        self.empty = not closes

    def __contains__(self, key: object) -> bool:
        return key == "Close"

    def __getitem__(self, key: str) -> FakeSeries:
        if key != "Close":
            raise KeyError(key)
        return FakeSeries(self._closes)


class FakeTicker:
    def __init__(
        self,
        *,
        fast_info: object,
        histories: dict[tuple[str, str], FakeFrame],
    ) -> None:
        self.fast_info = fast_info
        self._histories = histories

    def history(self, *, interval: str, period: str, auto_adjust: bool) -> FakeFrame:
        assert auto_adjust is False
        return self._histories.get((interval, period), FakeFrame([]))


def _source_set() -> MarketSourceSet:
    return MarketSourceSet.model_validate(
        {
            "pipeline": "markets",
            "source_set_id": "markets",
            "provider": "yfinance",
            "assets": [
                {
                    "id": "sp500",
                    "name": "S&P500",
                    "symbol": "ES=F",
                    "group": "indices",
                    "ath": {
                        "symbol": "^GSPC",
                        "period": "10y",
                        "label": "S&P500",
                    },
                }
            ],
        }
    )


def test_yfinance_retriever_uses_fast_info_and_ath_history() -> None:
    tickers: dict[str, Any] = {
        "ES=F": FakeTicker(
            fast_info={"lastPrice": 110.0, "previousClose": 100.0},
            histories={},
        ),
        "^GSPC": FakeTicker(
            fast_info={},
            histories={("1d", "10y"): FakeFrame([80.0, 100.0, 90.0])},
        ),
    }
    retriever = YahooFinanceRetriever(lambda symbol: tickers[symbol])

    snapshot = retriever.retrieve(
        _source_set(),
        run_id="run-1",
        retrieved_at=datetime(2026, 8, 26, 18, 0, tzinfo=UTC),
    )

    asset = snapshot.assets[0]
    assert asset.last == 110.0
    assert asset.previous_close == 100.0
    assert asset.error is None
    assert asset.ath_last == 90.0
    assert asset.ath_high == 100.0


def test_yfinance_retriever_falls_back_to_history() -> None:
    tickers: dict[str, Any] = {
        "ES=F": FakeTicker(
            fast_info={},
            histories={
                ("5m", "5d"): FakeFrame([109.0, 110.0]),
                ("1d", "6mo"): FakeFrame([95.0, 100.0]),
            },
        ),
        "^GSPC": FakeTicker(
            fast_info={},
            histories={("1d", "10y"): FakeFrame([80.0, 100.0, 90.0])},
        ),
    }
    retriever = YahooFinanceRetriever(lambda symbol: tickers[symbol])

    snapshot = retriever.retrieve(
        _source_set(),
        run_id="run-1",
        retrieved_at=datetime(2026, 8, 26, 18, 0, tzinfo=UTC),
    )

    asset = snapshot.assets[0]
    assert asset.last == 110.0
    assert asset.previous_close == 95.0
    assert asset.error is None
