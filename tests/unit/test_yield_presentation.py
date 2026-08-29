from datetime import UTC, datetime

from daily_dash.config import YieldProfile
from daily_dash.contracts import YieldLevel, YieldReportData, YieldSpread
from daily_dash.presentation.yields import render_yield_report


def test_yield_report_highlights_current_euro_financial_stress_proxy() -> None:
    profile = YieldProfile.model_validate(
        {
            "profile_id": "yields",
            "pipeline": "yields",
            "source_set": "yields",
            "presentation": {"title": "Yield Report"},
        }
    )
    report = YieldReportData(
        run_id="run-1",
        profile="yields",
        generated_at=datetime(2026, 8, 31, 16, 3, tzinfo=UTC),
        levels=[
            YieldLevel(series_id=series_id, name=name)
            for series_id, name in (
                ("us-3m", "US 3M"),
                ("us-2y", "US 2Y"),
                ("us-10y", "US 10Y"),
                ("de-2y", "Germany 2Y"),
                ("de-10y", "Germany 10Y"),
                ("eur-aaa-3m", "Euro AAA 3M"),
                ("eur-aaa-2y", "Euro AAA 2Y"),
                ("eur-aaa-10y", "Euro AAA 10Y"),
                ("eur-all-10y", "Euro all-ratings 10Y"),
            )
        ],
        spreads=[
            YieldSpread(spread_id=spread_id, name=name)
            for spread_id, name in (
                ("us-eur-3m", "US 3M − Euro AAA 3M"),
                ("us-de-2y", "US 2Y − Germany 2Y"),
                ("us-de-10y", "US 10Y − Germany 10Y"),
                ("us-10y-3m", "US 10Y − 3M"),
                ("us-10y-2y", "US 10Y − 2Y"),
                ("de-10y-2y", "Germany 10Y − 2Y"),
                ("eur-aaa-10y-3m", "Euro AAA 10Y − 3M"),
                ("eur-aaa-10y-2y", "Euro AAA 10Y − 2Y"),
            )
        ]
        + [
            YieldSpread(
                spread_id="eur-all-aaa-10y",
                name="Euro all-ratings 10Y − AAA 10Y",
                value_pp=0.43,
                change_bp=2.0,
                signal="neutral",
            )
        ],
    )

    artifact = render_yield_report(report, profile)

    assert "*Financial stress*" in artifact.content
    assert "Euro all-ratings 10Y − AAA 10Y" in artifact.content
    assert "0.43 pp" in artifact.content
    assert "+2 bp" in artifact.content
    assert "Italy 10Y" not in artifact.content
