from __future__ import annotations

from zoneinfo import ZoneInfo

from daily_dash.config import YahooMoversProfile
from daily_dash.contracts import (
    ArtifactFormat,
    MoverSection,
    MoversReportData,
    ReportArtifact,
)


def _entry_line(index: int, symbol: str, name: str, price: float, change_pct: float) -> str:
    return f"{index:>2}. {symbol:<6} {price:>10.2f}  {change_pct:>+7.2f}%  {name}"


def _section_lines(section: MoverSection) -> list[str]:
    lines = [f"*{section.name}*", "```"]
    lines.extend(
        _entry_line(index + 1, entry.symbol, entry.name, entry.price, entry.change_pct)
        for index, entry in enumerate(section.movers)
    )
    lines.append("```")
    return lines


def render_movers_report(report: MoversReportData, profile: YahooMoversProfile) -> ReportArtifact:
    local_time = report.generated_at.astimezone(ZoneInfo(profile.presentation.timezone))

    lines = [
        f"*{profile.presentation.title}*",
        f"_{local_time:%Y-%m-%d %H:%M} {profile.presentation.timezone}_",
        "",
        "_Top movers — rank, symbol, price, change, name_",
        "",
    ]
    for index, section in enumerate(report.sections):
        if index > 0:
            lines.append("")
        lines.extend(_section_lines(section))

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
            "section_count": len(report.sections),
            "mover_count": sum(len(section.movers) for section in report.sections),
            "issue_count": len(report.issues),
        },
    )
