from __future__ import annotations

from daily_dash.config import MarketsProfile
from daily_dash.contracts import ArtifactFormat, ReportArtifact
from daily_dash.contracts.market import MarketReportData, ProcessedMarketAsset


def _format_number(value: float | None, decimals: int = 2, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{value:.{decimals}f}{suffix}"


def _format_change(value: float | None, threshold: float) -> str:
    if value is None:
        return "—"
    if value >= threshold:
        return f"🟢{value:+.2f}%"
    if value <= -threshold:
        return f"🔴{value:+.2f}%"
    return f"{value:+.2f}%"


def _build_table(headers: list[str], rows: list[list[str]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, column in enumerate(row):
            widths[index] = max(widths[index], len(column))

    head = "   ".join(headers[index].ljust(widths[index]) for index in range(len(headers)))
    separator = "   ".join("-" * widths[index] for index in range(len(headers)))

    output = ["```\n" + head, separator]
    for row in rows:
        aligned: list[str] = []
        for index, column in enumerate(row):
            if index == 1:
                aligned.append(column.rjust(widths[index]))
            else:
                aligned.append(column.ljust(widths[index]))
        output.append("   ".join(aligned))
    output.append("```")
    return "\n".join(output)


def _ath_rows(assets: list[ProcessedMarketAsset]) -> list[list[str]]:
    rows: list[list[str]] = []
    for asset in assets:
        if asset.ath_symbol is None:
            continue
        rows.append(
            [
                asset.ath_label or asset.name,
                _format_number(asset.ath_distance_pct, 2, "%"),
            ]
        )
    return rows


def render_markets_report(report: MarketReportData, profile: MarketsProfile) -> ReportArtifact:
    presentation = profile.presentation
    timestamp = report.generated_at.strftime("%Y-%m-%d %H:%M")

    lines = [f"*{presentation.title}*  _({timestamp})_", ""]

    market_rows = [
        [
            asset.name,
            _format_number(asset.last, asset.price_decimals),
            _format_change(asset.change_pct, presentation.change_highlight_threshold_pct),
        ]
        for asset in report.assets
    ]
    lines.append(_build_table(["Asset", "Last", "Δ% vs Close"], market_rows))

    ath_rows = _ath_rows(report.assets)
    if ath_rows:
        lines.extend(["", "*Distance to ATH*", _build_table(["Asset", "Dist"], ath_rows)])

    if report.issues and presentation.data_issue_limit > 0:
        displayed = report.issues[: presentation.data_issue_limit]
        lines.extend(["", "_⚠️ Data issues:_", "```", *displayed])
        remaining = len(report.issues) - len(displayed)
        if remaining > 0:
            lines.append(f"... +{remaining} more")
        lines.append("```")

    return ReportArtifact(
        run_id=report.run_id,
        profile=report.profile,
        format=ArtifactFormat.MARKDOWN,
        content="\n".join(lines),
        created_at=report.generated_at,
        metadata={"asset_count": len(report.assets), "issue_count": len(report.issues)},
    )
