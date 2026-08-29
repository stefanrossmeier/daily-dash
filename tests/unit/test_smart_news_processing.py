from datetime import UTC, datetime

from pydantic import HttpUrl

from daily_dash.contracts.common import SourceKind
from daily_dash.contracts.smart_news import SmartNewsModelTheme
from daily_dash.contracts.source import SourceItem
from daily_dash.processing.smart_news import (
    build_llm_input_for_themes,
    materialize_smart_themes,
    select_macro_themes,
    select_smart_articles,
)


def _item(
    item_id: str,
    title: str,
    *,
    source: str = "Source",
    text: str = "",
    url: str | None = None,
    hour: int = 10,
) -> SourceItem:
    return SourceItem(
        id=item_id,
        source=source,
        source_kind=SourceKind.RSS,
        title=title,
        text=text,
        url=HttpUrl(url or f"https://example.test/{item_id}"),
        published_at=datetime(2026, 8, 28, hour, 0, tzinfo=UTC),
        retrieved_at=datetime(2026, 8, 28, 12, 0, tzinfo=UTC),
    )


def test_smart_article_selection_preserves_link_dedupe_and_newest_first() -> None:
    items = [
        _item("old", "Older", url="https://example.test/shared", hour=8),
        _item("new-duplicate", "New duplicate", url="https://example.test/shared", hour=11),
        _item("new", "Newest", hour=12),
    ]

    selected = select_smart_articles(items, limit=10)

    assert [item.id for item in selected] == ["new", "old"]


def test_llm_input_keeps_source_title_and_summary_like_legacy_smart_news() -> None:
    articles = [
        _item(
            "oil",
            "Oil falls on ceasefire hopes",
            source="FT World",
            text="Crude prices declined as traders watched Middle East talks.",
        )
    ]

    block = build_llm_input_for_themes(articles)

    assert "1) [FT World] Oil falls on ceasefire hopes" in block
    assert "Summary: Crude prices declined" in block


def test_legacy_macro_filter_keeps_broad_theme_and_drops_narrow_corporate_theme() -> None:
    articles = [
        _item(
            "oil",
            "Oil falls as Middle East ceasefire hopes rise",
            source="FT World",
            text="Energy markets and risk sentiment react to Iran ceasefire talks.",
        ),
        _item(
            "airlines",
            "Airlines gain as crude prices decline",
            source="CNBC Markets",
            text="Lower oil prices support airlines as energy costs ease.",
        ),
        _item(
            "uber",
            "Uber expands Delivery Hero stake via Prosus deal",
            source="MarketWatch Top Stories",
            text="The transaction changes one company stake.",
        ),
    ]
    themes = [
        SmartNewsModelTheme(
            title="Middle East ceasefire hopes push oil lower and improve risk sentiment",
            summary=(
                "Oil prices fell as ceasefire hopes improved risk sentiment and reduced "
                "near-term energy supply fears. Airlines reacted to lower fuel costs."
            ),
            headline_indices=[1, 2],
        ),
        SmartNewsModelTheme(
            title="Uber expands Delivery Hero stake via Prosus deal",
            summary="Uber changed its stake through a corporate transaction.",
            headline_indices=[3],
        ),
    ]

    selected = select_macro_themes(articles, themes, max_themes=5)

    assert [theme.title for theme in selected] == [themes[0].title]

    materialized = materialize_smart_themes(articles, selected)
    assert materialized[0].supporting_headlines[0].headline_link == "https://example.test/oil"
