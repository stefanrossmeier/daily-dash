from daily_dash.config.models import XWatchlistRankingConfig
from daily_dash.contracts.x_watchlist import XWatchlistModelEvaluation
from daily_dash.processing.x_watchlist import (
    score_x_watchlist_evaluations,
    select_x_watchlist_ids,
)


def _item(
    id_: str,
    topic: str,
    *,
    relevance: int = 80,
    impact: int = 70,
    breadth: int = 60,
    info: int = 80,
) -> XWatchlistModelEvaluation:
    return XWatchlistModelEvaluation(
        id=id_,
        relevance=relevance,
        market_impact=impact,
        market_breadth=breadth,
        information_value=info,
        category="macro",
        urgency="high",
        topic_key=topic,
        rationale="useful",
    )


def test_scores_and_filters_semantic_market_signal() -> None:
    config = XWatchlistRankingConfig()
    evaluations = score_x_watchlist_evaluations(
        [
            _item("good", "fed"),
            _item("weak", "noise", relevance=30, impact=20, breadth=10, info=30),
        ],
        config,
    )
    by_id = {item.id: item for item in evaluations}
    assert by_id["good"].eligible is True
    assert by_id["weak"].eligible is False
    assert by_id["good"].semantic_score > by_id["weak"].semantic_score


def test_relaxed_defaults_keep_potentially_useful_distinct_topic() -> None:
    config = XWatchlistRankingConfig()
    evaluations = score_x_watchlist_evaluations(
        [
            _item(
                "interesting",
                "market-structure",
                relevance=55,
                impact=35,
                breadth=50,
                info=45,
            )
        ],
        config,
    )
    assert evaluations[0].semantic_score == 0.4575
    assert evaluations[0].eligible is True


def test_relaxed_defaults_still_reject_contextless_chatter() -> None:
    config = XWatchlistRankingConfig()
    evaluations = score_x_watchlist_evaluations(
        [_item("chatter", "other", relevance=6, impact=4, breadth=5, info=5)],
        config,
    )
    assert evaluations[0].eligible is False


def test_selection_limits_repeated_topics_without_forcing_quota() -> None:
    config = XWatchlistRankingConfig(max_items_per_topic=1)
    scored = score_x_watchlist_evaluations(
        [_item("a", "fed"), _item("b", "fed"), _item("c", "oil")],
        config,
    )
    selected = select_x_watchlist_ids(scored, limit=10, max_items_per_topic=1)
    assert len(selected) == 2
    assert "c" in selected
