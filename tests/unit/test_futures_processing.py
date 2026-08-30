from datetime import UTC, datetime

import pytest

from daily_dash.config import FuturesProfile
from daily_dash.contracts.futures import RawFuturesQuote, RawFuturesSnapshot
from daily_dash.processing.futures import process_futures_snapshot


def _profile() -> FuturesProfile:
    return FuturesProfile.model_validate(
        {
            "profile_id": "futures",
            "pipeline": "futures",
            "source_set": "futures",
            "presentation": {},
        }
    )


def test_futures_processing_uses_previous_daily_close_math() -> None:
    raw = RawFuturesSnapshot(
        run_id="run-1",
        source_set="futures",
        retrieved_at=datetime(2026, 8, 28, 21, 15, tzinfo=UTC),
        quotes=[
            RawFuturesQuote(
                asset_id="sp500",
                name="S&P",
                instrument="future",
                last=5100.0,
                previous_value=5000.0,
                change_basis="previous_close",
                source="TradingView",
                source_ref="CME_MINI:ES1!",
                data_type="tradingview_1h",
            )
        ],
    )
    report = process_futures_snapshot(raw, _profile())
    assert report.quotes[0].change_pct == pytest.approx(2.0)
    assert report.quotes[0].status == "ok"
    assert report.quotes[0].change_basis == "previous_close"


def test_futures_processing_marks_missing_previous_close_partial() -> None:
    raw = RawFuturesSnapshot(
        run_id="run-1",
        source_set="futures",
        retrieved_at=datetime(2026, 8, 28, 21, 15, tzinfo=UTC),
        quotes=[
            RawFuturesQuote(
                asset_id="dax",
                name="DAX",
                instrument="future",
                last=26000.0,
                change_basis="unavailable",
                source="TradingView",
                source_ref="EUREX:FDAX1!",
                data_type="tradingview_1h",
                error="no previous close",
            )
        ],
    )
    report = process_futures_snapshot(raw, _profile())
    assert report.quotes[0].change_pct is None
    assert report.quotes[0].status == "partial"
    assert report.issues == ["DAX (EUREX:FDAX1!): no previous close"]
