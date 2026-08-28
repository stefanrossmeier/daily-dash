from __future__ import annotations

from zoneinfo import ZoneInfo

from daily_dash.config import WeekendMarketsProfile
from daily_dash.contracts import ArtifactFormat, ReportArtifact, WeekendMarketReportData


def _number(value: float | None, decimals: int) -> str:
    if value is None:
        return "—"
    return f"{value:.{decimals}f}"


def _change(value: float | None, threshold: float) -> str:
    if value is None:
        return "—"
    if value >= threshold:
        return f"🟢{value:+.2f}%"
    if value <= -threshold:
        return f"🔴{value:+.2f}%"
    return f"{value:+.2f}%"


def render_weekend_markets_report(
    report: WeekendMarketReportData,
    profile: WeekendMarketsProfile,
) -> ReportArtifact:
    local_time = report.generated_at.astimezone(ZoneInfo(profile.presentation.timezone))
    lines = [
        f"*{profile.presentation.title}*",
        f"_{local_time:%Y-%m-%d %H:%M} {profile.presentation.timezone}_",
        "",
    ]

    for quote in report.quotes:
        lines.extend(
            [
                f"*{quote.name}*",
                (
                    f"Bid {_number(quote.bid, quote.price_decimals)} · "
                    f"Ask {_number(quote.ask, quote.price_decimals)} · "
                    f"{
                        _change(
                            quote.change_pct,
                            profile.presentation.change_highlight_threshold_pct,
                        )
                    }"
                ),
                "",
            ]
        )

    if report.issues and profile.presentation.data_issue_limit > 0:
        displayed = report.issues[: profile.presentation.data_issue_limit]
        lines.append("⚠️ Data issues")
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
        metadata={"quote_count": len(report.quotes), "issue_count": len(report.issues)},
    )
