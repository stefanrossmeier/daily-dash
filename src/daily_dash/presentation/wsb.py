from __future__ import annotations

from html import escape
from zoneinfo import ZoneInfo

from daily_dash.contracts.common import ArtifactFormat
from daily_dash.contracts.report import ReportArtifact
from daily_dash.contracts.wsb import WsbRunDocument

_SIGNAL_LABELS = {
    "broad-market": "🌐 Broad market",
    "market-moving-bet": "🎯 Market-moving bet",
    "both": "🔥 Broad + positioning",
    "narrow-or-irrelevant": "Narrow",
}


def render_wsb_report(document: WsbRunDocument) -> ReportArtifact:
    local = document.retrieved_at.astimezone(ZoneInfo(document.timezone))
    title = f"🎲 <b>WSB — Signals & Hot Topics</b> · {local:%Y-%m-%d %H:%M}"
    post_by_id = {post.id: post for post in document.candidates}
    eval_by_id = {item.id: item for item in document.evaluations}
    lines = [title]

    if not document.selected_ids:
        lines.extend(
            [
                "",
                "Keine WSB-Threads haben heute die Schwelle für Markt-Signale oder "
                "außergewöhnliche Aktivität erreicht.",
            ]
        )
    else:
        for index, post_id in enumerate(document.selected_ids, start=1):
            post = post_by_id[post_id]
            evaluation = eval_by_id[post_id]
            if evaluation.extreme_activity_eligible and not evaluation.market_eligible:
                label = "🔥 Extrem heiß auf WSB"
            elif evaluation.extreme_activity_eligible:
                label = f"{_SIGNAL_LABELS[evaluation.signal_type]} · 🔥 Extrem heiß"
            else:
                label = _SIGNAL_LABELS[evaluation.signal_type]
            lines.extend(
                [
                    "",
                    f'{index}) <a href="{escape(post.url, quote=True)}">{escape(post.title)}</a>',
                    f"{label} · Signal {evaluation.selection_score:.2f}",
                    (
                        f"Impact {evaluation.market_impact} · "
                        f"Breadth {evaluation.market_breadth} · "
                        f"WSB-Signal {evaluation.positioning_signal}"
                    ),
                    f"{post.num_comments} 💬 · {post.score} ⬆️",
                    escape(evaluation.rationale),
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
