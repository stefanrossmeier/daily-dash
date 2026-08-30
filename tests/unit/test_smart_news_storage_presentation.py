from datetime import UTC, datetime
from pathlib import Path

from pydantic import HttpUrl

from daily_dash.config.loader import load_news_profile
from daily_dash.contracts.common import SourceKind
from daily_dash.contracts.smart_news import (
    SmartNewsRetrievalWindow,
    SmartNewsRunDocument,
    SmartNewsTheme,
)
from daily_dash.contracts.source import SourceItem
from daily_dash.presentation.smart_news import render_smart_news_report
from daily_dash.storage.smart_news import JsonSmartNewsRunStore

ROOT = Path(__file__).resolve().parents[2]


def _profile():
    return load_news_profile(ROOT / "config/profiles/news-smart.yaml")


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
    report = render_smart_news_report(_document(), _profile())

    assert "DailyDash Smart News Themes" in report.content
    assert "Oil and ceasefire talks dominate markets" in report.content
    assert "Oil prices fell as ceasefire talks advanced." in report.content
    assert "supporting" not in report.content.lower()
    assert report.metadata["parse_mode"] == "HTML"


def test_smart_news_empty_report_has_explicit_message() -> None:
    document = _document().model_copy(
        update={"articles": [], "article_count": 0, "themes": [], "theme_count": 0}
    )

    report = render_smart_news_report(document, _profile())

    assert "Keine relevanten neuen Headlines im Betrachtungszeitraum" in report.content


def test_smart_news_without_themes_falls_back_to_headlines() -> None:
    document = _document().model_copy(update={"themes": [], "theme_count": 0})

    report = render_smart_news_report(document, _profile())

    assert "Keine klaren Themen erkannt" in report.content
    assert "Oil falls as ceasefire talks advance" in report.content
