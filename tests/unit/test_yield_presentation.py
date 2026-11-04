from datetime import UTC, date, datetime

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
                ("fr-2y", "France 2Y"),
                ("fr-10y", "France 10Y"),
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
                ("fr-de-2y", "France 2Y − Germany 2Y"),
                ("fr-de-10y", "France 10Y − Germany 10Y"),
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
    assert "EUa-EU 10Y" in artifact.content
    assert "0.43pp" in artifact.content
    assert "+2bp" in artifact.content
    assert "Italy 10Y" not in artifact.content


def _fr_report() -> tuple[YieldReportData, YieldProfile]:
    profile = YieldProfile.model_validate(
        {
            "profile_id": "yields",
            "pipeline": "yields",
            "source_set": "yields",
            "presentation": {"title": "Yield Report"},
        }
    )
    report = YieldReportData(
        run_id="run-fr",
        profile="yields",
        generated_at=datetime(2026, 8, 31, 16, 3, tzinfo=UTC),
        levels=[
            YieldLevel(
                series_id=series_id,
                name=name,
                observed_on=date(2026, 8, 31),
                value_pct=value,
                change_bp=change,
            )
            for series_id, name, value, change in (
                ("us-3m", "US 3M", 4.10, 2.0),
                ("us-2y", "US 2Y", 3.90, -3.0),
                ("us-10y", "US 10Y", 4.20, 1.0),
                ("de-2y", "Germany 2Y", 2.10, 0.0),
                ("de-10y", "Germany 10Y", 2.70, 4.0),
                ("eur-aaa-3m", "Euro AAA 3M", 2.90, 1.0),
                ("eur-aaa-2y", "Euro AAA 2Y", 2.20, -1.0),
                ("eur-aaa-10y", "Euro AAA 10Y", 3.00, 2.0),
                ("eur-all-10y", "Euro all-ratings 10Y", 3.30, 2.0),
                ("fr-2y", "France 2Y", 3.20, 10.0),
                ("fr-10y", "France 10Y", 3.55, 5.0),
            )
        ],
        spreads=[
            YieldSpread(
                spread_id=spread_id,
                name=name,
                observed_on=date(2026, 8, 31),
                value_pp=value,
                change_bp=change,
                signal="neutral",
            )
            for spread_id, name, value, change in (
                ("us-eur-3m", "US 3M − Euro AAA 3M", 1.20, 1.0),
                ("us-de-2y", "US 2Y − Germany 2Y", 1.80, -3.0),
                ("us-de-10y", "US 10Y − Germany 10Y", 1.50, -3.0),
                ("fr-de-2y", "France 2Y − Germany 2Y", 1.10, 10.0),
                ("fr-de-10y", "France 10Y − Germany 10Y", 0.85, 1.0),
                ("us-10y-3m", "US 10Y − 3M", 0.10, -1.0),
                ("us-10y-2y", "US 10Y − 2Y", 0.30, 4.0),
                ("de-10y-2y", "Germany 10Y − 2Y", 0.60, 4.0),
                ("eur-aaa-10y-3m", "Euro AAA 10Y − 3M", 0.10, 1.0),
                ("eur-aaa-10y-2y", "Euro AAA 10Y − 2Y", 0.80, 3.0),
                ("eur-all-aaa-10y", "Euro all-ratings 10Y − AAA 10Y", 0.30, 0.0),
            )
        ],
    )
    return report, profile


def test_france_rows_rendered_compact() -> None:
    artifact = render_yield_report(*_fr_report())
    content = artifact.content

    assert "FR 2Y" in content
    assert "FR 10Y" in content
    assert "3.20%" in content
    assert "+10bp" in content
    assert "26-08-31" in content
    assert "FR-DE 2Y" in content
    assert "FR-DE 10Y" in content
    assert "1.10pp" in content
    assert "0.85pp" in content
    # Short dates in data rows; only the report header keeps the full date.
    level_block = content.split("```")[1]
    assert "26-08-31" in level_block
    assert "2026-08-31" not in level_block


def test_every_data_row_fits_one_line() -> None:
    artifact = render_yield_report(*_fr_report())

    data_lines = [
        line
        for block in artifact.content.split("```")[1::2]
        for line in block.splitlines()
        if line.strip()
    ]
    assert data_lines
    for line in data_lines:
        assert len(line) <= 40, f"line too long for one Telegram row: {line!r}"


def test_country_codes_used_in_level_rows() -> None:
    artifact = render_yield_report(*_fr_report())
    level_block = artifact.content.split("```")[1]

    for label in (
        "US 3M",
        "US 2Y",
        "US 10Y",
        "DE 2Y",
        "DE 10Y",
        "FR 2Y",
        "FR 10Y",
        "EU 3M",
        "EU 2Y",
        "EU 10Y",
        "EUa 10Y",
    ):
        assert f"{label:<8}" in level_block, f"missing compact level label {label}"
    for long_name in ("Germany", "France", "Euro AAA", "Euro all-ratings"):
        assert long_name not in level_block


def test_new_spreads_render_in_cross_market_block() -> None:
    artifact = render_yield_report(*_fr_report())
    cross_block = artifact.content.split("*Cross-market spreads*")[1].split("*Term spreads*")[0]

    assert "US-DE 2Y" in cross_block
    assert "US-DE 10Y" in cross_block
    assert "FR-DE 2Y" in cross_block
    assert "FR-DE 10Y" in cross_block
    assert "US-EU 3M" in cross_block
    assert "⚪ FR-DE 2Y" in cross_block
    assert "⚪ FR-DE 10Y" in cross_block


def test_sections_and_metadata_unchanged() -> None:
    artifact = render_yield_report(*_fr_report())
    content = artifact.content

    for heading in (
        "*Levels — yield / Δ / date*",
        "*Cross-market spreads*",
        "*Term spreads*",
        "*Financial stress*",
    ):
        assert heading in content
    assert "EU = Euro AAA" in content
    assert artifact.metadata["level_count"] == 11
    assert artifact.metadata["spread_count"] == 11
