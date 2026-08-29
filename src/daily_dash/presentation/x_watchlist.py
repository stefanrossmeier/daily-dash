from __future__ import annotations

from html import escape
from zoneinfo import ZoneInfo

from daily_dash.contracts.common import ArtifactFormat
from daily_dash.contracts.report import ReportArtifact
from daily_dash.contracts.x_watchlist import XWatchlistRunDocument

_TITLE = "X Watchlist"


def render_x_watchlist_report(document: XWatchlistRunDocument) -> ReportArtifact:
    zone = ZoneInfo(document.timezone)
    local = document.retrieved_at.astimezone(zone)
    post_by_id = {post.id: post for post in document.candidates}
    lines = [f"𝕏 <b>{escape(_TITLE)}</b> · {local:%Y-%m-%d %H:%M}"]

    if not document.selected_ids:
        lines.extend(["", "No selected X posts in this window."])
    else:
        for post_id in document.selected_ids:
            post = post_by_id[post_id]
            published = post.publication_time.astimezone(zone)
            lines.extend(
                [
                    "",
                    f"<b>@{escape(post.author_handle)}</b> · {published:%H:%M}",
                    escape(post.post_text.strip()),
                    f'<a href="{escape(post.post_url, quote=True)}">Open on X</a>',
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
