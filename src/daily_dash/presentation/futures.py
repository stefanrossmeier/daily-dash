from __future__ import annotations

from zoneinfo import ZoneInfo

from daily_dash.config import FuturesProfile
from daily_dash.contracts import ArtifactFormat, ReportArtifact
from daily_dash.contracts.futures import FuturesReportData


def _format_number(value: float | None, decimals: int) -> str:
    return "—" if value is None else f"{value:.{decimals}f}"


def _format_change(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f}%"


def _build_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, column in enumerate(row):
            widths[index] = max(widths[index], len(column))
    lines = ["```"]
    lines.append("   ".join(headers[index].ljust(widths[index]) for index in range(len(headers))))
    lines.append("   ".join("-" * width for width in widths))
    for row in rows:
        lines.append(
            "   ".join(
                column.rjust(widths[index]) if index in {1, 2} else column.ljust(widths[index])
                for index, column in enumerate(row)
            )
        )
    lines.append("```")
    return "\n".join(lines)


def render_futures_report(report: FuturesReportData, profile: FuturesProfile) -> ReportArtifact:
    presentation = profile.presentation
    timezone = ZoneInfo(presentation.timezone)
    timestamp = report.generated_at.astimezone(timezone).strftime("%Y-%m-%d %H:%M")
    rows = [
        [
            quote.name,
            _format_number(quote.last, quote.price_decimals),
            _format_change(quote.change_pct),
        ]
        for quote in report.quotes
    ]
    lines = [
        f"*{presentation.title}*  _({timestamp} Berlin)_",
        "",
        _build_table(["Asset", "Last", "Δ%"], rows),
        "_TradingView 1h bars. Δ% vs prior daily close._",
    ]

    if report.issues and presentation.data_issue_limit > 0:
        displayed = report.issues[: presentation.data_issue_limit]
        lines.extend(["", "_⚠️ Data issues:_", "```", *displayed])
        remaining = len(report.issues) - len(displayed)
        if remaining > 0:
            lines.append(f"... +{remaining} more")
        lines.append("```")

    unavailable_count = sum(1 for quote in report.quotes if quote.last is None)
    return ReportArtifact(
        run_id=report.run_id,
        profile=report.profile,
        format=ArtifactFormat.MARKDOWN,
        content="\n".join(lines),
        created_at=report.generated_at,
        metadata={
            "asset_count": len(report.quotes),
            "issue_count": len(report.issues),
            "unavailable_count": unavailable_count,
            "source": "TradingView via tvDatafeed",
        },
    )
