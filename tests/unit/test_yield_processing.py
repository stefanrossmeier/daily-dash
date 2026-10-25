from datetime import UTC, date, datetime

from daily_dash.config import YieldProfile
from daily_dash.contracts import RawYieldSeries, RawYieldSnapshot, YieldObservation
from daily_dash.processing.yields import process_yield_snapshot


def _series(series_id: str, name: str, values: list[tuple[str, float]]) -> RawYieldSeries:
    return RawYieldSeries(
        series_id=series_id,
        name=name,
        provider="test",
        source_ref=f"test:{series_id}",
        observations=[
            YieldObservation(observed_on=date.fromisoformat(day), value_pct=value)
            for day, value in values
        ],
    )


def _profile() -> YieldProfile:
    return YieldProfile.model_validate(
        {
            "profile_id": "yields",
            "pipeline": "yields",
            "source_set": "yields",
            "presentation": {"curve_lookback_points": 2},
        }
    )


def test_cross_market_spread_uses_common_dates_and_previous_common_date() -> None:
    raw = RawYieldSnapshot(
        run_id="run-1",
        source_set="yields",
        retrieved_at=datetime(2026, 8, 31, 18, 3, tzinfo=UTC),
        series=[
            _series(
                "us-10y",
                "US 10Y",
                [("2026-08-31", 4.20), ("2026-08-28", 4.00), ("2026-08-27", 3.80)],
            ),
            _series(
                "de-10y",
                "Germany 10Y",
                [("2026-08-28", 2.50), ("2026-08-27", 2.40)],
            ),
        ],
    )

    report = process_yield_snapshot(raw, _profile())
    spread = next(spread for spread in report.spreads if spread.spread_id == "us-de-10y")

    assert spread.observed_on == date(2026, 8, 28)
    assert spread.value_pp == 1.50
    assert round(spread.change_bp or 0.0, 8) == 10.0
    assert spread.signal == "red"


def test_us_curve_regime_uses_aligned_observations() -> None:
    raw = RawYieldSnapshot(
        run_id="run-2",
        source_set="yields",
        retrieved_at=datetime(2026, 8, 31, 18, 3, tzinfo=UTC),
        series=[
            _series("us-2y", "US 2Y", [("2026-08-31", 3.90), ("2026-08-28", 4.05)]),
            _series("us-10y", "US 10Y", [("2026-08-31", 4.20), ("2026-08-28", 4.18)]),
        ],
    )

    report = process_yield_snapshot(raw, _profile())

    assert report.curve_regime is not None
    assert "Bull Steepener" in report.curve_regime.label


def _fr_de_snapshot(**overrides: list[tuple[str, float]]) -> RawYieldSnapshot:
    series_defs = {
        "fr-2y": ("France 2Y", [("2026-08-31", 3.20), ("2026-08-28", 3.10)]),
        "fr-10y": ("France 10Y", [("2026-08-31", 3.55), ("2026-08-28", 3.50)]),
        "de-2y": ("Germany 2Y", [("2026-08-31", 2.10), ("2026-08-28", 2.00)]),
        "de-10y": ("Germany 10Y", [("2026-08-31", 2.70), ("2026-08-28", 2.60)]),
    }
    for series_id, values in overrides.items():
        series_defs[series_id] = (series_defs[series_id][0], values)
    return RawYieldSnapshot(
        run_id="run-fr",
        source_set="yields",
        retrieved_at=datetime(2026, 8, 31, 18, 3, tzinfo=UTC),
        series=[
            _series(series_id, name, values)
            for series_id, (name, values) in series_defs.items()
        ],
    )


def test_france_levels_computed_with_bp_change() -> None:
    report = process_yield_snapshot(_fr_de_snapshot(), _profile())

    fr2 = next(level for level in report.levels if level.series_id == "fr-2y")
    fr10 = next(level for level in report.levels if level.series_id == "fr-10y")

    assert fr2.name == "France 2Y"
    assert fr2.observed_on == date(2026, 8, 31)
    assert fr2.value_pct == 3.20
    assert round(fr2.change_bp or 0.0, 8) == 10.0
    assert fr10.value_pct == 3.55
    assert round(fr10.change_bp or 0.0, 8) == 5.0


def test_france_minus_germany_spreads_are_france_higher_positive() -> None:
    report = process_yield_snapshot(_fr_de_snapshot(), _profile())

    spread2 = next(s for s in report.spreads if s.spread_id == "fr-de-2y")
    spread10 = next(s for s in report.spreads if s.spread_id == "fr-de-10y")

    assert spread2.name == "France 2Y − Germany 2Y"
    assert spread2.observed_on == date(2026, 8, 31)
    assert round(spread2.value_pp, 8) == 1.10
    assert spread2.value_pp > 0  # France yields higher ⇒ positive
    assert round(spread2.change_bp or 0.0, 8) == 0.0  # 3.10-2.00=1.10 same level
    assert spread10.value_pp == 0.85
    assert spread10.signal == "neutral"


def test_france_germany_spread_uses_shared_dates_only() -> None:
    # French latest (08-31) has no German counterpart on that date:
    # the spread must use the newest shared date (08-28), never subtract
    # across different dates. fr-2y also carries an 08-27 observation so a
    # previous shared date exists for the bp change.
    raw = _fr_de_snapshot(
        **{
            "fr-2y": [("2026-08-31", 3.20), ("2026-08-28", 3.10), ("2026-08-27", 3.10)],
            "de-2y": [("2026-08-28", 2.00), ("2026-08-27", 2.05)],
            "de-10y": [("2026-08-28", 2.60), ("2026-08-27", 2.55)],
        }
    )
    report = process_yield_snapshot(raw, _profile())

    spread2 = next(s for s in report.spreads if s.spread_id == "fr-de-2y")
    assert spread2.observed_on == date(2026, 8, 28)
    assert round(spread2.value_pp, 8) == round(3.10 - 2.00, 8)
    # Previous shared date 08-27: fr 3.10 - de 2.05 = 1.05 → change +5 bp
    assert round(spread2.change_bp or 0.0, 8) == 5.0


def test_france_germany_spread_missing_when_no_shared_dates() -> None:
    raw = _fr_de_snapshot(
        **{"de-2y": [("2026-08-20", 2.00)], "de-10y": [("2026-08-20", 2.60)]}
    )
    report = process_yield_snapshot(raw, _profile())

    for spread_id in ("fr-de-2y", "fr-de-10y"):
        spread = next(s for s in report.spreads if s.spread_id == spread_id)
        assert spread.value_pp is None
        assert spread.observed_on is None
        assert spread.change_bp is None


def test_missing_french_series_records_issues_and_placeholders() -> None:
    raw = RawYieldSnapshot(
        run_id="run-fr-missing",
        source_set="yields",
        retrieved_at=datetime(2026, 8, 31, 18, 3, tzinfo=UTC),
        series=[
            _series("de-2y", "Germany 2Y", [("2026-08-31", 2.10)]),
            _series("de-10y", "Germany 10Y", [("2026-08-31", 2.70)]),
        ],
    )
    report = process_yield_snapshot(raw, _profile())

    for series_id in ("fr-2y", "fr-10y"):
        level = next(level for level in report.levels if level.series_id == series_id)
        assert level.value_pct is None
        assert level.observed_on is None
        assert level.change_bp is None
    for spread_id in ("fr-de-2y", "fr-de-10y"):
        spread = next(s for s in report.spreads if s.spread_id == spread_id)
        assert spread.value_pp is None
    issues_text = " ".join(report.issues)
    assert "France 2Y" in issues_text
    assert "France 10Y" in issues_text


def test_existing_levels_and_spreads_preserved_with_france_added() -> None:
    report = process_yield_snapshot(_fr_de_snapshot(), _profile())

    level_ids = [level.series_id for level in report.levels]
    for existing in (
        "us-3m", "us-2y", "us-10y", "de-2y", "de-10y",
        "eur-aaa-3m", "eur-aaa-2y", "eur-aaa-10y", "eur-all-10y",
    ):
        assert existing in level_ids
    spread_ids = [spread.spread_id for spread in report.spreads]
    for existing in (
        "us-eur-3m", "us-de-2y", "us-de-10y", "us-10y-3m", "us-10y-2y",
        "de-10y-2y", "eur-aaa-10y-3m", "eur-aaa-10y-2y", "eur-all-aaa-10y",
    ):
        assert existing in spread_ids
