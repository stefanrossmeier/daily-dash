from __future__ import annotations

from zoneinfo import ZoneInfo

from daily_dash.config import YieldProfile
from daily_dash.contracts import (
    ArtifactFormat,
    ReportArtifact,
    YieldLevel,
    YieldReportData,
    YieldSpread,
)


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}%"


def _pp(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f} pp"


def _bp(value: float | None) -> str:
    return "—" if value is None else f"{value:+.0f} bp"


def _signal(signal: str) -> str:
    return {"green": "🟢", "orange": "🟠", "red": "🔴"}.get(signal, "⚪")


def _level_line(level: YieldLevel) -> str:
    date_text = "—" if level.observed_on is None else level.observed_on.isoformat()
    return f"{level.name:<20} {_pct(level.value_pct):>7}  {_bp(level.change_bp):>8}  {date_text}"


def _spread_line(spread: YieldSpread) -> str:
    date_text = "—" if spread.observed_on is None else spread.observed_on.isoformat()
    return (
        f"{_signal(spread.signal)} {spread.name:<30} "
        f"{_pp(spread.value_pp):>8}  {_bp(spread.change_bp):>8}  {date_text}"
    )


def render_yield_report(report: YieldReportData, profile: YieldProfile) -> ReportArtifact:
    local_time = report.generated_at.astimezone(ZoneInfo(profile.presentation.timezone))
    levels = {level.series_id: level for level in report.levels}
    spreads = {spread.spread_id: spread for spread in report.spreads}

    lines = [
        f"*{profile.presentation.title}*",
        f"_{local_time:%Y-%m-%d %H:%M} {profile.presentation.timezone}_",
        "",
        "*Levels — yield / Δ previous observation / date*",
        "```",
    ]
    for group, ids in (
        ("US", ("us-3m", "us-2y", "us-10y")),
        ("Germany", ("de-2y", "de-10y")),
        ("Euro AAA", ("eur-aaa-3m", "eur-aaa-2y", "eur-aaa-10y")),
        ("Euro all-ratings", ("eur-all-10y",)),
    ):
        lines.append(group)
        lines.extend(_level_line(levels[series_id]) for series_id in ids)
    lines.extend(["```", "", "*Cross-market spreads*", "```"])
    lines.extend(
        _spread_line(spreads[spread_id]) for spread_id in ("us-eur-3m", "us-de-2y", "us-de-10y")
    )
    lines.extend(["```", "", "*Term spreads*", "```"])
    lines.extend(
        _spread_line(spreads[spread_id])
        for spread_id in (
            "us-10y-3m",
            "us-10y-2y",
            "de-10y-2y",
            "eur-aaa-10y-3m",
            "eur-aaa-10y-2y",
        )
    )

    lines.extend(["```", "", "*Financial stress*", "```"])
    lines.append(_spread_line(spreads["eur-all-aaa-10y"]))
    lines.append("```")

    if report.curve_regime is not None:
        lines.extend(
            [
                "",
                "*US Yield Curve Regime*",
                f"- {report.curve_regime.label}",
                (
                    f"  Δ2Y {_bp(report.curve_regime.delta_2y_pp * 100.0)} · "
                    f"Δ10Y {_bp(report.curve_regime.delta_10y_pp * 100.0)}"
                ),
                f"  {report.curve_regime.description}",
            ]
        )

    if report.issues and profile.presentation.data_issue_limit > 0:
        displayed = report.issues[: profile.presentation.data_issue_limit]
        lines.extend(["", "⚠️ Data issues"])
        lines.extend(f"- {issue}" for issue in displayed)
        remaining = len(report.issues) - len(displayed)
        if remaining > 0:
            lines.append(f"- ... +{remaining} more")

    return ReportArtifact(
        run_id=report.run_id,
        profile=report.profile,
        format=ArtifactFormat.MARKDOWN,
        content="\n".join(lines).rstrip(),
        created_at=report.generated_at,
        metadata={
            "level_count": len(report.levels),
            "spread_count": len(report.spreads),
            "issue_count": len(report.issues),
        },
    )
