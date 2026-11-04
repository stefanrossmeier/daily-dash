from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from daily_dash.config import YieldProfile
from daily_dash.contracts import (
    ArtifactFormat,
    ReportArtifact,
    YieldLevel,
    YieldReportData,
    YieldSpread,
)

# Compact two-letter country labels keep every series on a single line in
# Telegram's narrow code blocks. EU = Euro AAA, EUa = Euro all-ratings.
LEVEL_LABELS = {
    "us-3m": "US 3M",
    "us-2y": "US 2Y",
    "us-10y": "US 10Y",
    "de-2y": "DE 2Y",
    "de-10y": "DE 10Y",
    "fr-2y": "FR 2Y",
    "fr-10y": "FR 10Y",
    "eur-aaa-3m": "EU 3M",
    "eur-aaa-2y": "EU 2Y",
    "eur-aaa-10y": "EU 10Y",
    "eur-all-10y": "EUa 10Y",
}

SPREAD_LABELS = {
    "us-eur-3m": "US-EU 3M",
    "us-de-2y": "US-DE 2Y",
    "us-de-10y": "US-DE 10Y",
    "fr-de-2y": "FR-DE 2Y",
    "fr-de-10y": "FR-DE 10Y",
    "us-10y-3m": "US 10Y-3M",
    "us-10y-2y": "US 10Y-2Y",
    "de-10y-2y": "DE 10Y-2Y",
    "eur-aaa-10y-3m": "EU 10Y-3M",
    "eur-aaa-10y-2y": "EU 10Y-2Y",
    "eur-all-aaa-10y": "EUa-EU 10Y",
}


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}%"


def _pp(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}pp"


def _bp(value: float | None) -> str:
    return "—" if value is None else f"{value:+.0f}bp"


def _signal(signal: str) -> str:
    return {"green": "🟢", "orange": "🟠", "red": "🔴"}.get(signal, "⚪")


def _short_date(observed_on: date | None) -> str:
    return "—" if observed_on is None else f"{observed_on:%y-%m-%d}"


def _level_line(level: YieldLevel) -> str:
    label = LEVEL_LABELS.get(level.series_id, level.name)
    return (
        f"{label:<8} {_pct(level.value_pct):>7}  "
        f"{_bp(level.change_bp):>7}  {_short_date(level.observed_on)}"
    )


def _spread_line(spread: YieldSpread) -> str:
    label = SPREAD_LABELS.get(spread.spread_id, spread.name)
    # Telegram renders the signal emoji ~2 columns wide; keeping the whole
    # row at <= 34 display columns prevents mid-row wraps on narrow phones.
    return (
        f"{_signal(spread.signal)}{label:<10}{_pp(spread.value_pp):>7} "
        f"{_bp(spread.change_bp):>5} {_short_date(spread.observed_on)}"
    )


def render_yield_report(report: YieldReportData, profile: YieldProfile) -> ReportArtifact:
    local_time = report.generated_at.astimezone(ZoneInfo(profile.presentation.timezone))
    levels = {level.series_id: level for level in report.levels}
    spreads = {spread.spread_id: spread for spread in report.spreads}

    lines = [
        f"*{profile.presentation.title}*",
        f"_{local_time:%Y-%m-%d %H:%M} {profile.presentation.timezone}_",
        "",
        "*Levels — yield / Δ / date*",
        "```",
    ]
    for series_id in (
        "us-3m",
        "us-2y",
        "us-10y",
        "de-2y",
        "de-10y",
        "fr-2y",
        "fr-10y",
        "eur-aaa-3m",
        "eur-aaa-2y",
        "eur-aaa-10y",
        "eur-all-10y",
    ):
        lines.append(_level_line(levels[series_id]))
    lines.extend(
        [
            "```",
            "_EU = Euro AAA, EUa = Euro all-ratings_",
            "",
            "*Cross-market spreads*",
            "```",
        ]
    )
    lines.extend(
        _spread_line(spreads[spread_id])
        for spread_id in ("us-eur-3m", "us-de-2y", "us-de-10y", "fr-de-2y", "fr-de-10y")
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
        # Issue text can contain raw URLs with underscores that Telegram
        # legacy Markdown would parse as entity starts; a code fence keeps
        # the text raw and delivery reliable.
        lines.extend(["", "⚠️ Data issues", "```"])
        lines.extend(f"- {issue}" for issue in displayed)
        remaining = len(report.issues) - len(displayed)
        if remaining > 0:
            lines.append(f"- ... +{remaining} more")
        lines.append("```")

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
