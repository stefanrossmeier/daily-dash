from datetime import UTC, datetime

from daily_dash.config import MarketsProfile
from daily_dash.contracts import MarketGroup, MarketReportData, ProcessedMarketAsset
from daily_dash.presentation.markets import render_markets_report


def _profile() -> MarketsProfile:
    return MarketsProfile.model_validate(
        {
            "schema_version": 1,
            "profile_id": "markets",
            "pipeline": "markets",
            "source_set": "markets",
            "presentation": {
                "title": "Market Snapshot",
                "timezone": "Europe/Berlin",
                "change_highlight_threshold_pct": 1.0,
                "data_issue_limit": 8,
            },
        }
    )


def test_market_report_preserves_legacy_presentation_elements() -> None:
    report = MarketReportData(
        run_id="run-1",
        profile="markets",
        generated_at=datetime(2026, 8, 26, 18, 0, tzinfo=UTC),
        assets=[
            ProcessedMarketAsset(
                asset_id="eurusd",
                name="EURUSD",
                symbol="EURUSD=X",
                group=MarketGroup.FX,
                price_decimals=4,
                last=1.17234,
                change_pct=1.2,
            ),
            ProcessedMarketAsset(
                asset_id="btc",
                name="BTC",
                symbol="BTC-USD",
                group=MarketGroup.CRYPTO,
                last=100000.0,
                change_pct=-1.5,
                ath_label="Bitcoin",
                ath_symbol="BTC-USD",
                ath_distance_pct=-12.34,
            ),
        ],
        issues=["Example: no prev close"],
    )

    artifact = render_markets_report(report, _profile())

    assert "*Market Snapshot*" in artifact.content
    assert "EURUSD" in artifact.content
    assert "1.1723" in artifact.content
    assert "🟢+1.20%" in artifact.content
    assert "🔴-1.50%" in artifact.content
    assert "*Distance to ATH*" in artifact.content
    assert "Bitcoin" in artifact.content
    assert "-12.34%" in artifact.content
    assert "⚠️ Data issues" in artifact.content
