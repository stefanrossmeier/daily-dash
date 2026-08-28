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

    for position, item_id in enumerate(document.selected_ids, start=1):
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

    if document.duplicate_suppressions:
        count = len(document.duplicate_suppressions)
        noun = "duplicate article" if count == 1 else "duplicate articles"
        lines.append(f"<i>{count} {noun} suppressed by event identity.</i>")

    return ReportArtifact(
        run_id=document.run_id,
        profile=document.profile,
        format=ArtifactFormat.TELEGRAM,
        content="\n\n".join(lines),
        created_at=document.retrieved_at,
        metadata={
            "parse_mode": "HTML",
            "link_provenance": "source_item_url",
        },
    )
