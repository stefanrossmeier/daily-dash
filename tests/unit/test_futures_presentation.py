from datetime import UTC, datetime

from daily_dash.config import FuturesProfile
from daily_dash.contracts.futures import FuturesQuote, FuturesReportData
from daily_dash.presentation.futures import render_futures_report


def test_futures_presentation_matches_legacy_snapshot_shape() -> None:
    profile = FuturesProfile.model_validate(
        {
            "profile_id": "futures",
            "pipeline": "futures",
            "source_set": "futures",
            "presentation": {},
        }
    )
    report = FuturesReportData(
        run_id="run-1",
        profile="futures",
        generated_at=datetime(2026, 8, 28, 21, 15, tzinfo=UTC),
        quotes=[
            FuturesQuote(
                asset_id="sp500",
                name="S&P",
                instrument="ES",
                last=6500.25,
                previous_value=6467.91,
                change_pct=0.5,
                change_basis="previous_close",
                source="TradingView",
                source_ref="CME_MINI:ES1!",
                data_type="tradingview_1h",
                status="ok",
            ),
            FuturesQuote(
                asset_id="brent",
                name="Brent",
                instrument="Brent",
                source="TradingView",
                source_ref="NYMEX:BZ1!",
                status="unavailable",
            ),
        ],
        issues=["Brent (NYMEX:BZ1!): no last price"],
    )
    artifact = render_futures_report(report, profile)
    assert "*Futures Snapshot*  _(2026-08-28 23:15 Berlin)_" in artifact.content
    assert "S&P" in artifact.content
    assert "6500.25" in artifact.content
    assert "+0.50%" in artifact.content
    assert "Brent" in artifact.content
    assert "—" in artifact.content
    assert "_TradingView 1h bars. Δ% vs prior daily close._" in artifact.content
    assert "_⚠️ Data issues:_" in artifact.content
    assert "Brent (NYMEX:BZ1!): no last price" in artifact.content
    assert artifact.metadata["source"] == "TradingView via tvDatafeed"
