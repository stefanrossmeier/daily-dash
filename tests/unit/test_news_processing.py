from datetime import UTC, datetime, timedelta

from daily_dash.contracts.common import SourceKind
from daily_dash.contracts.news import NewsRankingContent, NewsRankingEvaluation
from daily_dash.contracts.source import SourceItem
from daily_dash.processing.news import (
    apply_top_market_policy,
    canonical_url,
    deduplicate_news_items,
    source_neutral_prefilter,
    top_market_selection_score,
)


def _item(
    item_id: str,
    source_id: str,
    title: str,
    url: str,
    minutes_ago: int,
) -> SourceItem:
    now = datetime(2026, 8, 27, 10, 0, tzinfo=UTC)
    return SourceItem(
        id=item_id,
        source=source_id,
        source_kind=SourceKind.RSS,
        title=title,
        text="summary",
        url=url,
        published_at=now - timedelta(minutes=minutes_ago),
        retrieved_at=now,
        metadata={"source_id": source_id},
    )


def test_canonical_url_removes_tracking() -> None:
    assert (
        canonical_url("https://EXAMPLE.com/a/?utm_source=rss&x=1#fragment")
        == "https://example.com/a?x=1"
    )


def test_dedupe_by_canonical_url_or_title() -> None:
    items = [
        _item(
            "a",
            "one",
            "Policy surprise",
            "https://example.test/a?utm_source=rss",
            1,
        ),
        _item(
            "b",
            "two",
            "Different title",
            "https://example.test/a",
            2,
        ),
        _item(
            "c",
            "three",
            "POLICY   SURPRISE",
            "https://example.test/c",
            3,
        ),
    ]
    assert [item.id for item in deduplicate_news_items(items)] == ["a"]


def test_source_neutral_prefilter_uses_recency_not_source_identity() -> None:
    items = [
        _item("a-old", "a", "A old", "https://x.test/a-old", 10),
        _item("b-new", "b", "B new", "https://x.test/b-new", 1),
        _item("a-new", "a", "A new", "https://x.test/a-new", 2),
    ]

    result = source_neutral_prefilter(items, limit=2)

    assert [item.id for item in result] == ["b-new", "a-new"]


def test_source_neutral_prefilter_rejects_non_positive_limit() -> None:
    import pytest

    with pytest.raises(ValueError, match="prefilter limit"):
        source_neutral_prefilter([], limit=0)


def _evaluation(
    item_id: str,
    *,
    rank_score: int,
    market_impact: int,
    market_breadth: int,
    relevance: int = 70,
    surprise: int = 60,
    novelty: int = 60,
    quality: int = 70,
) -> NewsRankingEvaluation:
    return NewsRankingEvaluation(
        id=item_id,
        event_key=item_id,
        rank_score=rank_score,
        tier=4,
        priority=rank_score,
        relevance=relevance,
        market_impact=market_impact,
        market_breadth=market_breadth,
        surprise=surprise,
        quality=quality,
        novelty=novelty,
        selected=True,
        rationale="Fixture.",
    )


def test_top_market_score_penalizes_narrow_impact_despite_high_rank_score() -> None:
    broad = _evaluation(
        "broad",
        rank_score=70,
        market_impact=70,
        market_breadth=75,
    )
    narrow = _evaluation(
        "narrow",
        rank_score=95,
        market_impact=30,
        market_breadth=25,
    )

    assert top_market_selection_score(broad) > top_market_selection_score(narrow)


def test_top_market_policy_orders_and_filters_from_model_values() -> None:
    ranking = NewsRankingContent(
        evaluations=[
            _evaluation(
                "narrow",
                rank_score=95,
                market_impact=30,
                market_breadth=25,
            ),
            _evaluation(
                "broad",
                rank_score=70,
                market_impact=70,
                market_breadth=75,
            ),
        ],
        ranking=["narrow", "broad"],
    )

    result = apply_top_market_policy(ranking, min_score=0.50)
    by_id = {item.id: item for item in result.evaluations}

    assert result.ranking == ["broad", "narrow"]
    assert by_id["broad"].selection_eligible is True
    assert by_id["narrow"].selection_eligible is False
    assert by_id["broad"].selection_score > by_id["narrow"].selection_score
