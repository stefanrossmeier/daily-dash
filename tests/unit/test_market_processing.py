from datetime import UTC, datetime

import pytest

from daily_dash.contracts import MarketGroup, RawMarketAsset, RawMarketSnapshot
from daily_dash.processing.markets import process_market_snapshot


def test_market_processing_calculates_change_and_ath_distance() -> None:
    snapshot = RawMarketSnapshot(
        run_id="run-1",
        source_set="markets",
        retrieved_at=datetime(2026, 8, 26, 18, 0, tzinfo=UTC),
        assets=[
            RawMarketAsset(
                asset_id="sp500",
                name="S&P500",
                symbol="ES=F",
                group=MarketGroup.INDICES,
                last=110.0,
                previous_close=100.0,
                ath_label="S&P500",
                ath_symbol="^GSPC",
                ath_period="10y",
                ath_last=90.0,
                ath_high=100.0,
            )
        ],
    )

    report = process_market_snapshot(snapshot, profile_id="markets")

    assert report.assets[0].change_pct == pytest.approx(10.0)
    assert report.assets[0].ath_distance_pct == pytest.approx(-10.0)
    assert report.issues == []


def test_market_processing_preserves_degraded_data_as_issue() -> None:
    snapshot = RawMarketSnapshot(
        run_id="run-1",
        source_set="markets",
        retrieved_at=datetime(2026, 8, 26, 18, 0, tzinfo=UTC),
        assets=[
            RawMarketAsset(
                asset_id="vix",
                name="VIX",
                symbol="^VIX",
                group=MarketGroup.VOLATILITY,
                error="no prev close",
            )
        ],
    )

    report = process_market_snapshot(snapshot, profile_id="markets")

    assert report.assets[0].change_pct is None
    assert report.issues == ["VIX (^VIX): no prev close"]
