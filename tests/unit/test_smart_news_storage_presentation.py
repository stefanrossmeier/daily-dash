from datetime import UTC, datetime

from pydantic import HttpUrl

from daily_dash.contracts.common import SourceKind
from daily_dash.contracts.smart_news import (
    SmartNewsRetrievalWindow,
    SmartNewsRunDocument,
    SmartNewsTheme,
)
from daily_dash.contracts.source import SourceItem
from daily_dash.presentation.smart_news import render_smart_news_report
from daily_dash.storage.smart_news import JsonSmartNewsRunStore


def _document() -> SmartNewsRunDocument:
    return SmartNewsRunDocument(
        run_id="smart-run-123",
        retrieved_at=datetime(2026, 8, 28, 12, 15, tzinfo=UTC),
        retrieval_window=SmartNewsRetrievalWindow(
            source="rolling",
            schedule_id="news-smart",
            timezone="Europe/Berlin",
            scheduled_for=datetime(2026, 8, 28, 10, 15, tzinfo=UTC),
            window_start=datetime(2026, 8, 27, 18, 15, tzinfo=UTC),
            window_end=datetime(2026, 8, 28, 12, 15, tzinfo=UTC),
            lookback_hours=18,
        ),
        source_diagnostics=[],
        retrieved_count=1,
        articles=[
            SourceItem(
                id="oil",
                source="FT World",
                source_kind=SourceKind.RSS,
                title="Oil falls as ceasefire talks advance",
                text="",
                url=HttpUrl("https://example.test/oil"),
                published_at=datetime(2026, 8, 28, 11, 0, tzinfo=UTC),
                retrieved_at=datetime(2026, 8, 28, 12, 15, tzinfo=UTC),
            )
        ],
        article_count=1,
        themes=[
            SmartNewsTheme(
                title="Oil and ceasefire talks dominate markets",
                llm_message="Oil prices fell as ceasefire talks advanced.",
                supporting_headlines=[],
            )
        ],
        theme_count=1,
    )


def test_smart_news_store_round_trips(tmp_path) -> None:
    document = _document()
    path = JsonSmartNewsRunStore(tmp_path).write(document)

    assert path.parent == tmp_path / "news/smart"
    assert JsonSmartNewsRunStore.read(path) == document


def test_smart_news_presentation_is_theme_only() -> None:
    report = render_smart_news_report(_document())

    assert "DailyDash Smart News Themes" in report.content
    assert "Oil and ceasefire talks dominate markets" in report.content
    assert "Oil prices fell as ceasefire talks advanced." in report.content
    assert "supporting" not in report.content.lower()
    assert report.metadata["parse_mode"] == "HTML"
