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
