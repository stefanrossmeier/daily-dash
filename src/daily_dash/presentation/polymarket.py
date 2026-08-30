from __future__ import annotations

from html import escape
from zoneinfo import ZoneInfo

from daily_dash.config.models import PolymarketProfile
from daily_dash.contracts.common import ArtifactFormat
from daily_dash.contracts.polymarket import PolymarketEventSnapshot, PolymarketRunDocument
from daily_dash.contracts.report import ReportArtifact


def _money(value: float) -> str:
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.0f}K"
    return f"${value:.0f}"


def _probability(event: PolymarketEventSnapshot) -> str | None:
    if event.representative_probability is None:
        return None
    outcome = event.representative_outcome or "Top"
    return f"{escape(outcome)} {event.representative_probability * 100:.0f}%"


def _move(value: float) -> str:
    return f"{value * 100:.1f}pp"


def render_polymarket_report(
    document: PolymarketRunDocument,
    profile: PolymarketProfile,
) -> ReportArtifact:
    local = document.retrieved_at.astimezone(ZoneInfo(document.timezone))
    lines = [f"🔮 <b>Polymarket</b> · {local:%Y-%m-%d %H:%M}"]

    lines.extend(["", "<b>Market Signals</b>"])
    if not document.signals:
        lines.append("No financially relevant Polymarket events were found in this report window.")
    else:
        for index, signal_selection in enumerate(
            document.signals[: profile.presentation.max_signal_items], start=1
        ):
            event = signal_selection.event
            probability = _probability(event)
            context = [f"24h Vol {_money(event.volume_24h)}"]
            if probability:
                context.insert(0, probability)
            lines.extend(
                [
                    "",
                    f'{index}) <a href="{escape(event.url, quote=True)}">{escape(event.title)}</a>',
                    " · ".join(context),
                ]
            )

    lines.extend(["", "<b>Hot on Polymarket</b>"])
    if not document.hot:
        lines.append("No unusually active Polymarket events were found in this report window.")
    else:
        for index, hot_selection in enumerate(
            document.hot[: profile.presentation.max_hot_items], start=1
        ):
            event = hot_selection.event
            context = [
                f"24h Vol {_money(event.volume_24h)}",
                f"Trades {event.recent_trades}",
                f"Comments {event.comment_count}",
                f"1h move {_move(event.max_abs_one_hour_price_change)}",
            ]
            lines.extend(
                [
                    "",
                    f'{index}) <a href="{escape(event.url, quote=True)}">{escape(event.title)}</a>',
                    " · ".join(context),
                ]
            )

    return ReportArtifact(
        run_id=document.run_id,
        profile=document.profile,
        format=ArtifactFormat.TELEGRAM,
        content="\n".join(lines),
        created_at=document.retrieved_at,
        metadata={"parse_mode": "HTML"},
    )
