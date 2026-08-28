from datetime import UTC, datetime
from pathlib import Path

from daily_dash.config.models import RssSourceConfig
from daily_dash.retrieval.rss import clean_feed_text, parse_feed_bytes

_REPO_ROOT = Path(__file__).parents[2]


def test_parse_rss_and_apply_lookback() -> None:
    data = (_REPO_ROOT / "tests" / "fixtures" / "news" / "sample.rss.xml").read_bytes()
    source = RssSourceConfig(
        id="fixture",
        name="Fixture",
        url="https://example.test/feed.xml",
        tags=["test"],
    )
    items = parse_feed_bytes(
        data,
        source=source,
        retrieved_at=datetime(2026, 8, 27, 10, 0, tzinfo=UTC),
        lookback_hours=8,
        max_items=20,
    )

    assert len(items) == 1
    assert items[0].title == "Central bank unexpectedly cuts rates"
    assert items[0].text == "A material policy surprise."
    assert items[0].metadata["source_id"] == "fixture"


def test_clean_feed_text_removes_html() -> None:
    assert clean_feed_text("<p>Hello&nbsp;<strong>world</strong></p>") == "Hello world"


def test_parse_rss_applies_half_open_explicit_window() -> None:
    data = (_REPO_ROOT / "tests" / "fixtures" / "news" / "sample.rss.xml").read_bytes()
    source = RssSourceConfig(
        id="fixture",
        name="Fixture",
        url="https://example.test/feed.xml",
    )

    included = parse_feed_bytes(
        data,
        source=source,
        retrieved_at=datetime(2026, 8, 27, 10, 0, tzinfo=UTC),
        window_start=datetime(2026, 8, 27, 7, 0, tzinfo=UTC),
        window_end=datetime(2026, 8, 27, 9, 0, tzinfo=UTC),
        max_items=20,
    )
    excluded_at_end = parse_feed_bytes(
        data,
        source=source,
        retrieved_at=datetime(2026, 8, 27, 10, 0, tzinfo=UTC),
        window_start=datetime(2026, 8, 27, 6, 0, tzinfo=UTC),
        window_end=datetime(2026, 8, 27, 8, 0, tzinfo=UTC),
        max_items=20,
    )

    assert [item.title for item in included] == ["Central bank unexpectedly cuts rates"]
    assert excluded_at_end == []
