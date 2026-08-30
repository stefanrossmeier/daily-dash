from __future__ import annotations

from html import escape

from daily_dash.config.models import NewsProfile
from daily_dash.contracts.common import ArtifactFormat
from daily_dash.contracts.news import NewsRunDocument
from daily_dash.contracts.report import ReportArtifact


def render_news_report(
    document: NewsRunDocument,
    profile: NewsProfile,
) -> ReportArtifact:
    """Render selected News items with links from the original SourceItems."""

    candidates = {item.id: item for item in document.candidates}
    lines = [f"<b>{escape(profile.presentation.title)}</b>"]

    if not document.selected_ids:
        lines.append("No relevant new articles were found in this report window.")

    backfill_ids = set(document.backfill_ids)
    backfill_started = False

    for position, item_id in enumerate(
        document.selected_ids[: profile.presentation.max_items], start=1
    ):
        if item_id in backfill_ids and not backfill_started:
            lines.append("<i>Backfill:</i>")
            backfill_started = True

        item = candidates.get(item_id)
        if item is None:
            raise ValueError(f"selected news item is missing from candidates: {item_id}")

        title = escape(item.title)
        source = escape(item.source)

        if item.url is None:
            headline = title
        else:
            original_url = escape(str(item.url), quote=True)
            headline = f'<a href="{original_url}">{title}</a>'

        lines.append(f"{position}. {headline} — <i>{source}</i>")

    return ReportArtifact(
        run_id=document.run_id,
        profile=document.profile,
        format=ArtifactFormat.TELEGRAM,
        content="\n\n".join(lines),
        created_at=document.retrieved_at,
        metadata={
            "parse_mode": "HTML",
            "link_provenance": "source_item_url",
            "backfill_count": len(document.backfill_ids),
        },
    )
