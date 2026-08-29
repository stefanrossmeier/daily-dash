from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from daily_dash.config import YieldProfile
from daily_dash.contracts import (
    RawYieldSeries,
    RawYieldSnapshot,
    YieldCurveRegime,
    YieldLevel,
    YieldObservation,
    YieldReportData,
    YieldSpread,
)


def _series_by_id(raw: RawYieldSnapshot) -> dict[str, RawYieldSeries]:
    return {series.series_id: series for series in raw.series}


def _level(series: RawYieldSeries | None, series_id: str, name: str) -> YieldLevel:
    if series is None or not series.observations:
        return YieldLevel(series_id=series_id, name=name)
    latest = series.observations[0]
    previous = series.observations[1] if len(series.observations) > 1 else None
    change_bp = None if previous is None else (latest.value_pct - previous.value_pct) * 100.0
    return YieldLevel(
        series_id=series_id,
        name=name,
        observed_on=latest.observed_on,
        value_pct=latest.value_pct,
        change_bp=change_bp,
    )


def _aligned_pairs(
    left: RawYieldSeries | None,
    right: RawYieldSeries | None,
) -> list[tuple[YieldObservation, YieldObservation]]:
    if left is None or right is None:
        return []
    right_by_date = {observation.observed_on: observation for observation in right.observations}
    pairs = [
        (observation, right_by_date[observation.observed_on])
        for observation in left.observations
        if observation.observed_on in right_by_date
    ]
    pairs.sort(key=lambda pair: pair[0].observed_on, reverse=True)
    return pairs


def _level_signal(
    value: float | None, green_hi: float, orange_hi: float
) -> Literal["green", "orange", "red", "neutral"]:
    if value is None:
        return "neutral"
    if value < green_hi:
        return "green"
    if value < orange_hi:
        return "orange"
    return "red"


def _inversion_signal(
    value: float | None, orange_mag: float = 0.25
) -> Literal["green", "orange", "red", "neutral"]:
    if value is None:
        return "neutral"
    if value > 0:
        return "green"
    if value >= -abs(orange_mag):
        return "orange"
    return "red"


def _spread(
    series: dict[str, RawYieldSeries],
    *,
    spread_id: str,
    name: str,
    left_id: str,
    right_id: str,
    signal_kind: str = "neutral",
    green_hi: float = 0.0,
    orange_hi: float = 0.0,
) -> YieldSpread:
    pairs = _aligned_pairs(series.get(left_id), series.get(right_id))
    if not pairs:
        return YieldSpread(spread_id=spread_id, name=name)

    latest_left, latest_right = pairs[0]
    value = latest_left.value_pct - latest_right.value_pct
    change_bp = None
    if len(pairs) > 1:
        previous_left, previous_right = pairs[1]
        previous_value = previous_left.value_pct - previous_right.value_pct
        change_bp = (value - previous_value) * 100.0

    signal: Literal["green", "orange", "red", "neutral"]
    if signal_kind == "inversion":
        signal = _inversion_signal(value)
    elif signal_kind == "level":
        signal = _level_signal(value, green_hi, orange_hi)
    else:
        signal = "neutral"

    return YieldSpread(
        spread_id=spread_id,
        name=name,
        observed_on=latest_left.observed_on,
        value_pp=value,
        change_bp=change_bp,
        signal=signal,
    )


def _curve_regime(
    series: dict[str, RawYieldSeries],
    *,
    lookback_points: int,
) -> YieldCurveRegime | None:
    pairs = _aligned_pairs(series.get("us-2y"), series.get("us-10y"))
    if len(pairs) < lookback_points:
        return None

    current_2y, current_10y = pairs[0]
    previous_2y, previous_10y = pairs[lookback_points - 1]
    delta_2y = current_2y.value_pct - previous_2y.value_pct
    delta_10y = current_10y.value_pct - previous_10y.value_pct
    threshold = 0.03

    if abs(delta_2y) < threshold and abs(delta_10y) < threshold:
        label = "⚪ Neutral / little curve movement"
        description = "No clear steepening or flattening over the lookback window."
    elif delta_10y > threshold and delta_10y > delta_2y + threshold:
        label = "🐻📈 Bear Steepener"
        description = "Long yields rose more than short yields; inflation or bond-selloff signal."
    elif delta_2y < -threshold and (delta_10y >= delta_2y or delta_10y > -threshold):
        label = "🐂📈 Bull Steepener"
        description = "Short yields fell more than long yields; easing/recession expectations."
    elif delta_2y > threshold and delta_2y > delta_10y + threshold:
        label = "🐻📉 Bear Flattener"
        description = "Short yields rose more than long yields; hawkish-policy signal."
    elif delta_10y < -threshold and delta_10y < delta_2y - threshold:
        label = "🐂📉 Bull Flattener"
        description = "Long yields fell more than short yields; safety/growth-risk signal."
    else:
        label = "⚪ Mixed curve signal"
        description = "No dominant steepening or flattening pattern."

    return YieldCurveRegime(
        label=label,
        delta_2y_pp=delta_2y,
        delta_10y_pp=delta_10y,
        description=description,
    )


def _issues(raw: RawYieldSnapshot, required_ids: Iterable[str]) -> list[str]:
    required = set(required_ids)
    issues: list[str] = []
    for series in raw.series:
        if series.error:
            issues.append(f"{series.name}: {series.error}")
        elif series.series_id in required and not series.observations:
            issues.append(f"{series.name}: no observations")
    return issues


def process_yield_snapshot(raw: RawYieldSnapshot, profile: YieldProfile) -> YieldReportData:
    series = _series_by_id(raw)
    level_specs = (
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
    levels = [_level(series.get(series_id), series_id, name) for series_id, name in level_specs]

    spreads = [
        _spread(
            series,
            spread_id="us-eur-3m",
            name="US 3M − Euro AAA 3M",
            left_id="us-3m",
            right_id="eur-aaa-3m",
            signal_kind="level",
            green_hi=1.0,
            orange_hi=2.0,
        ),
        _spread(
            series,
            spread_id="us-de-2y",
            name="US 2Y − Germany 2Y",
            left_id="us-2y",
            right_id="de-2y",
            signal_kind="level",
            green_hi=1.0,
            orange_hi=1.3,
        ),
        _spread(
            series,
            spread_id="us-de-10y",
            name="US 10Y − Germany 10Y",
            left_id="us-10y",
            right_id="de-10y",
            signal_kind="level",
            green_hi=0.8,
            orange_hi=1.3,
        ),
        _spread(
            series,
            spread_id="us-10y-3m",
            name="US 10Y − 3M",
            left_id="us-10y",
            right_id="us-3m",
            signal_kind="inversion",
        ),
        _spread(
            series,
            spread_id="us-10y-2y",
            name="US 10Y − 2Y",
            left_id="us-10y",
            right_id="us-2y",
            signal_kind="inversion",
        ),
        _spread(
            series,
            spread_id="de-10y-2y",
            name="Germany 10Y − 2Y",
            left_id="de-10y",
            right_id="de-2y",
            signal_kind="inversion",
        ),
        _spread(
            series,
            spread_id="eur-aaa-10y-3m",
            name="Euro AAA 10Y − 3M",
            left_id="eur-aaa-10y",
            right_id="eur-aaa-3m",
            signal_kind="inversion",
        ),
        _spread(
            series,
            spread_id="eur-aaa-10y-2y",
            name="Euro AAA 10Y − 2Y",
            left_id="eur-aaa-10y",
            right_id="eur-aaa-2y",
            signal_kind="inversion",
        ),
        _spread(
            series,
            spread_id="eur-all-aaa-10y",
            name="Euro all-ratings 10Y − AAA 10Y",
            left_id="eur-all-10y",
            right_id="eur-aaa-10y",
        ),
    ]

    return YieldReportData(
        run_id=raw.run_id,
        profile=profile.profile_id,
        generated_at=raw.retrieved_at,
        levels=levels,
        spreads=spreads,
        curve_regime=_curve_regime(
            series,
            lookback_points=profile.presentation.curve_lookback_points,
        ),
        issues=_issues(raw, (series_id for series_id, _ in level_specs)),
    )
