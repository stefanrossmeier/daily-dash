from __future__ import annotations

from html import escape
from zoneinfo import ZoneInfo

from daily_dash.config.models import WsbProfile
from daily_dash.contracts.common import ArtifactFormat
from daily_dash.contracts.report import ReportArtifact
from daily_dash.contracts.wsb import WsbRunDocument


def render_wsb_report(document: WsbRunDocument, profile: WsbProfile) -> ReportArtifact:
    local = document.retrieved_at.astimezone(ZoneInfo(document.timezone))
    title = f"🎲 <b>WSB</b> · {local:%Y-%m-%d %H:%M}"
    post_by_id = {post.id: post for post in document.candidates}
    lines = [title]

    if not document.selected_ids:
        lines.extend(
            [
                "",
                "No relevant or exceptionally active WSB threads were found in this report window.",
            ]
        )
    else:
        for index, post_id in enumerate(
            document.selected_ids[: profile.presentation.max_items], start=1
        ):
            post = post_by_id[post_id]
            lines.extend(
                [
                    "",
                    f'{index}) <a href="{escape(post.url, quote=True)}">{escape(post.title)}</a>',
                    f"{post.num_comments} 💬 · {post.score} ⬆️",
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
