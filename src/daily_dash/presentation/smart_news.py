from __future__ import annotations

from html import escape
from zoneinfo import ZoneInfo

from daily_dash.contracts.common import ArtifactFormat
from daily_dash.contracts.report import ReportArtifact
from daily_dash.contracts.smart_news import SmartNewsRunDocument


def render_smart_news_report(document: SmartNewsRunDocument) -> ReportArtifact:
    if not document.articles:
        content = (
            "📰 DailyDash Smart News: Keine relevanten neuen Headlines im Betrachtungszeitraum."
        )
    else:
        local_date = document.retrieved_at.astimezone(
            ZoneInfo(document.retrieval_window.timezone)
        ).strftime("%Y-%m-%d")
        lines = [f"📰 <b>DailyDash Smart News Themes — {local_date}</b>"]

        if not document.themes:
            lines.append("")
            lines.append("Keine klaren Themen erkannt, hier die wichtigsten Headlines:")
            for index, article in enumerate(document.articles[:8], start=1):
                lines.append(f"{index}) {escape(article.title)} ({escape(article.source)})")
        else:
            for theme in document.themes:
                lines.append("")
                lines.append(f"🔥 <b>{escape(theme.title)}</b>")
                if theme.llm_message:
                    lines.append(escape(theme.llm_message))

        content = "\n".join(lines)

    return ReportArtifact(
        run_id=document.run_id,
        profile=document.profile,
        format=ArtifactFormat.TELEGRAM,
        content=content,
        created_at=document.retrieved_at,
        metadata={
            "parse_mode": "HTML",
            "supporting_headlines_visible": False,
        },
    )
